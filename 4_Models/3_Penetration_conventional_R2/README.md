# DG penetration study (Fig. 7 of Yousaf et al. 2022)

Separate from the main study: the project "IEEE13 DSDR Fuse Coordination" and the `DSDR_Study/` folder are not changed.

| File | Content |
|---|---|
| `make_penetration_models.py` | Copies the replication project 7 times in PowerFactory (DG at 692 = 0, 10, 25, 37, 50, 75, 100 % of 4.05 MVA, conventional protection), runs load flow and faults, reads PowerFactory's relay/fuse times, exports each copy to `pfd/` (PowerFactory closed) |
| `sc_levels_penetration.py` | Every fault type at every node (bolted and LG through 3 ohm) in the seven models; currents at the fault, through R1, R2 and from the DG (PowerFactory closed) |
| `tcc_penetration.py` | TCC of the two Fig. 7 cases at every level -> `results/TCC_penetration_overview.png`, `TCC_penetration_633.png`, `TCC_penetration_671.png` |
| `compare_penetration.py` | Pickups by eq. (3) per level, short-circuit levels, minimum fault against pickup -> `results/Comparison_summary.md`, `Fig_pickup_sc.png` |
| `analyse_penetration.py` | CTI per level, ring % (each ring = 100 %), figures (Python only); the paper's values go to `comparison/` |
| `pfd/IEEE13_DG_penetration_XXX.pfd` | The seven PowerFactory models (import with File > Import > PFD) |
| `results/` | `penetration_results.json`, `Penetration_CTI.csv`, `Penetration_loadflow.csv`, `Fig07_penetration.png`, `Fig07_penetration_currents.png`, `Penetration_summary.md` |

Cases: 633 = LLL fault at 633, fuse F633 against R1 fast; 671 = LL fault at 684 on the lateral that leaves 671 through fuse F671-2, against R2 fast.
CTI = t_MMT(fuse) - t_fast(recloser); ring % = 100 x CTI / sum of |CTI| over the seven levels.
