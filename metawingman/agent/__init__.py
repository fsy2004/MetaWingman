"""MetaWingman Agent — the full-workflow evidence-synthesis agent.

The agent is a *decision* agent, not a classifier: it searches a network of
evidence, reasons open-world over candidate designs, and drives the whole
synthesis workflow, calling the E-R-V decision kernel at every stage.
"""
