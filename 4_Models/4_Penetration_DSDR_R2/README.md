# CTI against DG penetration with the DSDR

Companion of `../Penetration_Study` (conventional scheme). Same seven DG levels (0, 10, 25, 37, 50, 75,
100 % of 4.05 MVA) and the same two faults, but with the DSDR protection of the study: R2 with its forward
and reverse setting groups (designed for 100 % DG, not re-designed per level) and the fuses revised for
the DSDR (F633 400E; F671-2 stays 300E). The main project is only read.

| File | Content |
|---|---|
| `make_penetration_models_dsdr.py` | Seven PowerFactory copies "IEEE13 DSDR penetration NNN %", PowerFactory's own relay and fuse times, exported to `pfd/` (PowerFactory closed) |
| `analyse_dsdr_vs_conventional.py` | Comparison with the conventional study -> `results/CTI_conventional_vs_DSDR.csv`, `.png`, `Fig07_DSDR_ring.png`, `Summary.md` |

Result: at 633 the CTI against R1 stays positive at every level with the DSDR (+205 -> +43 ms) instead of
turning negative (+4 -> -51 ms), because of the larger fuse. Counting R2's reverse trip as well, the margin
is negative at 25 % and 37 % (-279, -14 ms): the reverse setting was designed for 100 % DG and its fast
curve is slow for the small DG current of a low penetration. At 671 (fault at 684) nothing changes: the
forward setting and F671-2 are the same in both schemes.
