"""MetaWingman training — method-trace learning aligned to external expert judge.

We train the agent on the *process* of published meta-analyses (method
trajectory), stripping the numeric outcome so it cannot learn answers — then
align it to an external heterogeneous reviewer judge via process-level DPO.
"""
