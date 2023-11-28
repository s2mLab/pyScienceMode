*****************
How to contribute
*****************

All contributions, bug reports, bug fixes, documentation improvements, enhancements, and ideas are welcome.
Your help is essential in keeping this project vibrant and relevant. Here are some guidelines for contributing.

Prerequisites
=============
Before starting, make sure you have:

- A GitHub account
- Basic understanding of Git (see `Git Tutorial <https://git-scm.com/docs/gittutorial>`_)
- Python installed on your machine (see `Python Downloads <https://www.python.org/downloads/>`_)

How to Contribute
------------------

1. **Fork the Project**: Start by forking the project on your own GitHub account.
2. **Clone the Fork**: Clone the fork onto your local machine.
3. **Set Up a Remote for the Fork**: Add the original remote as "upstream" to pull the latest changes if necessary (see `Configuring a Remote <https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/configuring-a-remote-for-a-fork>`_).
4. **Create a Branch**: Create a branch for your changes.
5. **Make Modifications**: Make your changes, adhering to the project's coding conventions and guidelines.
6. **Test Your Changes**: Run tests to ensure everything works as expected.
7. **Commit Your Changes**: Commit your changes with a descriptive commit message.
8. **Push to Your Fork**: Push your changes to your fork.
9. **Open a Pull Request (PR)**: Go to the original repo and open a pull request from your branch to the project's main branch.

Convention of coding
====================

`pyScienceMode` tries to follow as much as possible the PEP recommendations (https://www.python.org/dev/peps/).
Unless you have good reasons to disregard them, your pull-request is required to follow these recommendations.

All variable names that could be plural should be written as such.

Black is used to enforce the code spacing.
`pyScienceMode` is linted with the 120-character max per line's option.
This means that your pull-request tests on GitHub will appear to fail if black fails.
The easiest way to make sure black is happy is to locally run this command:
```
black . -l120 --exclude "external/*"
```
If you need to install black, you can do it via conda using the conda-forge channel.
