.. list-table::
   :widths: 33 33 33
   :header-rows: 1

   * - Feature
     - Rehastim2
     - RehastimP24
   * - Pulse width
     - [0, 500] **µs**
     - [10, 65520] **μs**
   * - Frequency
     - [1, 50] Hz for 8 channels
     - [0.5, 2000] **Hz** customizable
   * - Pulse form
     - Biphasic rectangular impulses width
     - Balanced biphasic square pulses or variable (adjustable using 16 discrete characteristic points)
   * - Communication speed
     - [20, 100] ms
     - [5,15] **ms**
   * - Interpulse interval
     - 8 ms per stimulation module
     - 5ms (can be modified)
   * - Serial port
     - USB with galvanic isolation
     - USB Type-C
   * - Behavior when several channels are activated with too high frequency
     - The stimulator will stimulate at the highest possible frequency that avoids overlap
     - Stimulation will not be active and the Rehastimp24 LED will be green.