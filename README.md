# Dual-Setting Directional Recloser and Fuse Coordination – IEEE 13-Node Feeder in DIgSILENT PowerFactory

**Author: Subash Khanal**

M.Sc. project in Power System Engineering, Department of Electrical Engineering, Pulchowk Campus,
Institute of Engineering, Tribhuvan University, October 2026.

The project implements and evaluates the protection strategy of

> M. Yousaf, A. Jalilian, K. M. Muttaqi, D. Sutanto, "An Adaptive Overcurrent Protection Scheme for
> Dual-Setting Directional Recloser and Fuse Coordination in Unbalanced Distribution Networks With
> Distributed Generation," *IEEE Trans. Ind. Appl.*, vol. 58, no. 2, pp. 1831–1842, 2022.
> doi:[10.1109/TIA.2022.3146095](https://doi.org/10.1109/TIA.2022.3146095)
> (the paper itself is not included in this repository)

on the IEEE 13-node test feeder in DIgSILENT PowerFactory 2021 SP2, with a 4.05 MVA synchronous DG at
node 692, commercial recloser relays (GE IAC77B801A, GE/Alstom CDG34) and fuses (Gould-Shawmut A055C),
unbalanced load-flow and short-circuit studies, and an EMT simulation of the reclosing sequence.

## Contents

| Folder | Contents |
| --- | --- |
| [`README.txt`](README.txt) | short overview of the folders |
| `1_Report/` | [`DSDR_Final_Report.pdf`](1_Report/DSDR_Final_Report.pdf) – final report (104 pages) |
| `2_Presentation/` | `DSDR_Final_Presentation.pptx` – 27 slides with speaker notes |
| `3_Guide_to_Run_the_Model/` | [`DSDR_Guide_Run_Model_and_Scripts.pdf`](3_Guide_to_Run_the_Model/DSDR_Guide_Run_Model_and_Scripts.pdf) – how to open the model and run the scripts |
| `4_Models/0_Benchmark_IEEE13_original/` | first model of the feeder and the first-attempt scripts (superseded) |
| `4_Models/1_Main_DSDR_Fuse_Coordination/` | **main model** (`01_MAIN_model_STANDIN_copy_DSDR_DG100pct.pfd`) and the scripts of the complete study |
| `4_Models/2_EMT_Fig10_time_domain/` | EMT projects of the reclosing sequence (Fig. 10), DG out and DG in |
| `4_Models/3_Penetration_conventional_R2/` | DG at 0, 10, 25, 37, 50, 75, 100 % with a single-setting R2 |
| `4_Models/4_Penetration_DSDR_R2/` | the same penetration levels with R2 as a dual-setting directional recloser |

## Main results

Out of 39 studied fault cells (every node × fault type), the fuse is saved in:

| Case | Cells held |
| --- | --- |
| Published fuse sizes, no DG | 35 of 39 |
| After the fuse revision (steps 8–10), no DG | 39 of 39 |
| DG connected, conventional single-setting R2 (Fig. 14) | 24 of 39 |
| DG connected, revised fuses, conventional R2 | 31 of 39 |
| DG connected, dual-setting R2 and revised fuses (Fig. 17) | **38 of 39** |
| Same settings, DG out of service | 37 of 39 |

The remaining cell, an LG fault at node 692, is limited by the delayed dial range of the recloser.
In the EMT simulation of an LL fault at 684, fuse F671-2 melts at 1.248 s without the DG and already at
0.752 s (during the second fast shot) with the DG.

## How to run

The full procedure is in the guide (folder 3). In short:

1. Copy `4_Models/1_Main_DSDR_Fuse_Coordination` to `C:\DSDR`.
2. In PowerFactory 2021 SP2 import `01_MAIN_model_STANDIN_copy_DSDR_DG100pct.pfd`, activate it and the study
   case **Study with Substation Transformer**.
3. In a Python Script object run `scripts\install_packages.py` once (matplotlib, reportlab), then
   `scripts\show_progress.py`. The report is printed in the Output Window and saved in `scripts\results\`,
   with `summary.txt`, Tables I–IV, the figures and the load-flow / short-circuit database.

`scripts\run_all.py` rebuilds the whole study from the bare network in engine mode (PowerFactory closed),
from the protection system to the EMT simulation.

## Testing (18 October 2026)

All files were tested on PowerFactory 2021 SP2 in engine mode, on copies, with the test projects removed
afterwards:

| Test | Result |
| --- | --- |
| All 60 Python scripts compile under Python 3.9; static check for undefined names | pass |
| All 19 `.pfd` models import, solve an unbalanced load flow and contain the expected reclosers, fuses and DG rating | pass |
| Guide procedure: import the ready model, run `show_progress.py` | pass after fix 1 – all six counts above reproduced; 1116 operating times, PowerFactory vs Python median deviation 0.02 %, max 1.22 % |
| Values quoted in the guide (load flow, 3-phase fault at 633, Fig. 10 melting times) | reproduced exactly |
| `run_all.py`, full rebuild from the bare network | pass after fixes 2 and 3 – all 11 steps complete |
| Report and guide PDFs, presentation | open; 104 / 4 pages, 27 slides with notes |

Fixes made during testing (`4_Models/1_Main_DSDR_Fuse_Coordination/scripts/`):

1. `pf_setup.py` (also its copies in folders 2–4): the scripts looked only for the project
   "IEEE13 DSDR Fuse Coordination", but the ready model imports as "IEEE13 DSDR penetration 100 %". Following
   the guide, `show_progress.py` then imported the bare network instead and stopped (`KeyError: 'DL'`).
   The scripts now use the imported model (the active project, or the ready model by name).
2. `step5_fig10_emt.py`: created the simulation-events folder when a fresh project has none (it stopped with
   `IndexError`).
3. `run_all.py`: removed seven steps whose scripts are not part of the delivered folder.

Notes:

* `IEEE 13 Node Feeder.pfd` (folder 1) and `IEEE13_original_benchmark.pfd` (folder 0) are described as the
  network without protection, but contain an earlier set of reclosers R1/R2 and 19 fuses. `step1_build_model.py`
  removes these before building the final protection, so the results are not affected.
* `make_ifmin_excel.py` additionally needs the `openpyxl` package, which `install_packages.py` does not install.
* The scripts in folders 2–4 document how those models were produced; several refer to the author's
  working folder `DSDR_Study` and are not meant to be re-run from the delivered folders. The models themselves
  are complete.
