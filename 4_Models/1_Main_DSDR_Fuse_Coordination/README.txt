MAIN MODEL - PowerFactory project 'IEEE13 DSDR Fuse Coordination', study case 'Study with Substation Transformer'.

01_MAIN_model_STANDIN_copy_DSDR_DG100pct.pfd   ready model: DG 100 %, R2 as dual-setting recloser, revised fuses
                                               (imports as 'IEEE13 DSDR penetration 100 %'; exported 3 October 2026
                                               from a copy of the main project - the project itself was never exported)
IEEE 13 Node Feeder.pfd                        the IEEE 13-node network without protection (starting point of the model)
scripts\                                       the Python scripts of the study (run inside PowerFactory, see the guide)
    show_progress.py                           runs the whole study (= script object 'Final(1)')
    install_packages.py                        installs matplotlib and reportlab, once

Copy this folder to C:\DSDR  (so that C:\DSDR\1_Main_DSDR_Fuse_Coordination\scripts\show_progress.py exists).
How to use: DSDR_Guide_Run_Model_and_Scripts.pdf in the main deliverables folder.
