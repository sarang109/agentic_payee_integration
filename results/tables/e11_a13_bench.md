### E11: PayeeBench A13 cases generated from the rational-deviation condition

| configuration   | losses   | with breach certificate   | refused   |
|:----------------|:---------|:--------------------------|:----------|
| M3              | 60/60    | 60/60                     | 0/60      |
| M5 (M3 + F6)    | 0/60     | -                         | 60/60     |

Each case gets a custodian and an exposure at which stealing pays at q = 0.5; M5 refuses the payment when the exposure exceeds the cap. M5's refusals of legitimate payments are in e11_refusal. q is an input, swept from 0.3 to 1, not a measurement. Simulation of an economic model; the numbers say nothing about any deployed custodian.
