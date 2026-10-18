"""Outcome Evaluation's held-out scenarios (SIP-0113 §4.1, §4.7; #2413).

A scenario is a job stated as a goal, with held-out steps and checks. A suite is a
content-addressed set of them, drafted by the supervisor and approved by the owner before use
(the 2.4 plan's D2). A campaign pins one suite when it is created.

The independence boundary is structural: no squad-side package imports this one
(``test_held_out_scenarios_stay_out_of_the_squads_reach.py``), and no route a squad identity
can call returns a scenario's steps.
"""
