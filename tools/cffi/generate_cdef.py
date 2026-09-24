"""Regenerate ``smpt_cdef.h``, the cffi ``cdef`` for the ScienceMode4 C library.

The cdef is committed so that building the extension only needs a C compiler,
CMake and the ``cffi`` Python package: no C preprocessor run, no MinGW/fake
Windows headers at build time. Re-run this script only when the
``extern/ScienceMode4_c_library`` submodule is bumped, then review the diff.

Usage (from the repository root)::

    pip install cffi pycparser        # plus a C preprocessor, see below
    python tools/cffi/generate_cdef.py

A C preprocessor is needed *only here*. By default the script tries, in order,
``$CPP``, ``cpp``, ``gcc -E``, ``clang -E`` and ``python -m ziglang cc -E``
(``pip install ziglang`` gives a portable one, handy on Windows without MSVC).

How it works:

* the public headers of the general, low-level and mid-level layers are
  preprocessed with ``-undef -nostdinc`` against the tiny stand-in libc of
  ``fake_libc/`` and a neutral POSIX profile (``__linux__``); the only
  platform-dependent struct (``Smpt_device``) is emitted opaque, so the result
  is valid on every OS;
* pycparser collects the typedefs coming from the library headers and the
  function prototypes of a whitelist of client headers;
* structs are emitted as *partial* (``...;``) and enum values as ``...`` so
  that, in cffi API mode, the real C compiler computes layouts and values on
  each platform (no ABI guessing);
* prototypes without a non-static definition in the library sources are
  dropped (some headers declare functions that are never implemented, which
  would fail at link time);
* the dyscom level (``smpt_dl_*``) is left out: its client header is only
  enabled for ``_WIN32``/``__linux__`` upstream, so it would break macOS.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from pycparser import c_ast, c_parser
from pycparser.c_generator import CGenerator

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LIB = ROOT / "extern" / "ScienceMode4_c_library" / "ScienceMode_Library"
INCLUDE = LIB / "include"
SRC = LIB / "src"
OUTPUT = HERE / "smpt_cdef.h"

LAYERS = ["general", "low-level", "mid-level"]
INCLUDE_DIRS = [
    INCLUDE / "general",
    INCLUDE / "general" / "packet",
    INCLUDE / "general" / "packet_input_buffer",
    INCLUDE / "general" / "packet_output_buffer",
    INCLUDE / "general" / "serial_port",
    INCLUDE / "low-level",
    INCLUDE / "mid-level",
]

# Headers pulled in for their types.
WRAPPER_HEADERS = [
    "smpt_definitions.h",
    "smpt_client.h",
    "smpt_client_utils.h",
    "smpt_client_power.h",
    "smpt_packet_number_generator.h",
    "smpt_ll_definitions.h",
    "smpt_ll_client.h",
    "smpt_ml_definitions.h",
    "smpt_ml_client.h",
]

# Headers whose function prototypes are exposed to Python (``lib.smpt_*``).
FUNCTION_HEADERS = {
    "smpt_client.h",
    "smpt_client_utils.h",
    "smpt_client_power.h",
    "smpt_packet_number_generator.h",
    "smpt_definitions_data_types.h",
    "smpt_definitions_power.h",
    "smpt_ll_client.h",
    "smpt_ll_definitions_data_types.h",
    "smpt_ml_client.h",
    "smpt_ml_definitions_data_types.h",
}

# Structs whose layout differs per platform: emitted fully opaque.
OPAQUE_STRUCTS = {"Smpt_device"}

DEFINES = ["-D__linux__=1", "-DSMPT_LOW_LEVEL", "-DSMPT_MID_LEVEL"]


def find_cpp() -> list[str]:
    if os.environ.get("CPP"):
        return shlex.split(os.environ["CPP"])
    for cand in (["cpp"], ["gcc", "-E"], ["clang", "-E"]):
        if shutil.which(cand[0]):
            return cand + (["-E"] if cand == ["cpp"] else [])
    try:
        import ziglang  # noqa: F401

        return [sys.executable, "-m", "ziglang", "cc", "-E"]
    except ImportError:
        sys.exit("No C preprocessor found: set $CPP or `pip install ziglang`.")


def preprocess() -> str:
    wrapper = "".join(f'#include "{h}"\n' for h in WRAPPER_HEADERS)
    cmd = find_cpp() + ["-undef", "-nostdinc", "-std=c99", "-x", "c", "-I", str(HERE / "fake_libc")]
    cmd += [f"-I{d}" for d in INCLUDE_DIRS] + DEFINES + ["-"]
    res = subprocess.run(cmd, input=wrapper, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        sys.exit(f"Preprocessing failed:\n{' '.join(cmd)}\n{res.stderr}")
    return res.stdout


def in_library(coord) -> bool:
    if coord is None or not coord.file:
        return False
    return Path(coord.file).resolve().is_relative_to(INCLUDE.resolve())


def defined_functions() -> set[str]:
    """Names of functions with a (non-static) definition in the C sources."""
    names = set()
    pattern = re.compile(r"^(?!static\b)[A-Za-z_][\w \t\*]*?\b(smpt_\w+)\s*\(", re.M)
    for layer in LAYERS:
        for c_file in (SRC / layer).rglob("*.c"):
            names.update(pattern.findall(c_file.read_text(encoding="utf-8", errors="replace")))
    return names


class Collector(c_ast.NodeVisitor):
    def __init__(self, implemented: set[str]):
        self.gen = CGenerator()
        self.implemented = implemented
        self.typedefs: list[str] = []
        self.functions: list[str] = []
        self.skipped: list[str] = []

    def visit_Typedef(self, node):
        if not in_library(node.coord):
            return
        inner = node.type.type if isinstance(node.type, c_ast.TypeDecl) else None
        if node.name in OPAQUE_STRUCTS:
            self.typedefs.append(f"typedef struct {{ ...; }} {node.name};")
            return
        if isinstance(inner, c_ast.Enum) and inner.values is not None:
            names = [e.name for e in inner.values.enumerators]
            body = ",\n    ".join(f"{n} = ..." for n in names)
            self.typedefs.append(f"typedef enum {{\n    {body}\n}} {node.name};")
            return
        if isinstance(inner, (c_ast.Struct, c_ast.Union)) and inner.decls is not None:
            kind = "struct" if isinstance(inner, c_ast.Struct) else "union"
            fields = []
            for decl in inner.decls:
                text = self.gen.visit(decl)
                # Array sizes are expressions on enum constants: let the compiler resolve them.
                text = re.sub(r"\[[^\]]+\]", "[...]", text)
                fields.append(f"    {text};")
            if kind == "struct":
                fields.append("    ...;")
            body = "\n".join(fields)
            self.typedefs.append(f"typedef {kind} {{\n{body}\n}} {node.name};")
            return
        self.typedefs.append(self.gen.visit(node) + ";")

    def visit_Decl(self, node):
        if not isinstance(node.type, c_ast.FuncDecl) or not in_library(node.coord):
            return
        if Path(node.coord.file).name not in FUNCTION_HEADERS:
            return
        if node.name not in self.implemented:
            self.skipped.append(node.name)
            return
        node.storage = []
        node.funcspec = []
        self.functions.append(self.gen.visit(node) + ";")


def main() -> None:
    if not INCLUDE.is_dir():
        sys.exit(f"{INCLUDE} not found: run `git submodule update --init`.")
    source = preprocess()
    # Keep line markers (they tell pycparser which header each decl comes from),
    # but drop GNU line-marker flags that pycparser does not understand.
    source = re.sub(r'^# (\d+) "(.*)".*$', r'#line \1 "\2"', source, flags=re.M)
    ast = c_parser.CParser().parse(source, filename="<wrapper>")
    collector = Collector(defined_functions())
    collector.visit(ast)

    sha = subprocess.run(
        ["git", "-C", str(LIB.parent), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    header = [
        "/* AUTO-GENERATED by tools/cffi/generate_cdef.py -- do not edit by hand.",
        f" * Source: ScienceMode4_c_library @ {sha or 'unknown'}",
        " * Layers: general, low-level (ll), mid-level (ml).",
        " * Regenerate: python tools/cffi/generate_cdef.py",
        " */",
        "",
    ]
    text = "\n".join(header + collector.typedefs + [""] + collector.functions) + "\n"
    OUTPUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}: {len(collector.typedefs)} typedefs, "
          f"{len(collector.functions)} functions.")
    if collector.skipped:
        print("Declared but not implemented (skipped):", ", ".join(sorted(collector.skipped)))


if __name__ == "__main__":
    main()
