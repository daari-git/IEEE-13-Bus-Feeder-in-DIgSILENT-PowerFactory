# Fig. 10 – EMT study in separate PowerFactory projects

Fig. 10 (current at node 632 for a line-to-line a–c fault at 684 through 0.2 Ω, two fast
shots of R2, then fuse F671-2) needs simulation events and the relays and fuses out of service. To keep
that away from the protection studies it lives in its own projects; the main project is left in
its normal state (no events, protection and DG in service).

| Project (PowerFactory) | File | Case | Switching times (s) |
|---|---|---|---|
| IEEE13 Fig10 EMT - DG out | `pfd/IEEE13_Fig10_EMT_DG_out.pfd` | without DG | fault 0.300; R2 open 0.420 / 0.740, close 0.620 / 0.940; F671-2 clears 1.613 |
| IEEE13 Fig10 EMT - DG in | `pfd/IEEE13_Fig10_EMT_DG_in.pfd` | DG 4.05 MVA in service | fault 0.300; R2 open 0.426 / 0.753, close 0.626 / 0.953; F671-2 clears 1.253 |

In each project: study case *Study with Substation Transformer*, event list with the six events, result
file *Fig10 EMT* (LOHL650-632, phase currents a and c at the 632 end) and the plot page *Curve plot*.
Open the project, run Initial Conditions and Start Simulation (2 s), and the plot fills.

Switching times: from R2's fast curve and the fuse heating of the simulated current (`DSDR_Study/step5_fig10_emt.py`).

`make_fig10_projects.py` rebuilds both projects from the user's set-up in the main project and
then restores the main project (PowerFactory closed). `results/` holds the waveforms and
`Fig10_DG_out_and_in.png`.

With the DG in service the current after the fuse has cleared oscillates (about 2.8 kA peak): the
low-inertia DG (Table I, M = 1.5 s) swings after the 1-s disturbance; it is not a fault current.
