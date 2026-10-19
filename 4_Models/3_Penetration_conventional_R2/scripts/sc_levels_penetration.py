"""
Short-circuit levels at every node of the seven penetration models (made by make_penetration_models.py).

For each copy "IEEE13 DG penetration NNN %" (only calculations, the models are not changed):
  * maximum faults: LG, LL, LLG, LLL, bolted, every phase combination the node has;
  * minimum faults: LG through 3 ohm (If,min);
  * for each fault: current at the fault, through R1, through R2 (with its direction) and from the DG.
Direction at R2: + = towards 671 (forward), - = towards 632 (reverse), from the active power at R2's end.

Output: results/sc_levels.json.  PowerFactory must be closed.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "DSDR_Study"))
from pf_setup import get_app, attr, STUDY_CASE           # noqa: E402
from protection_data import NODES, NODE_ORDER, PF_FAULT   # noqa: E402

LEVELS = [0, 10, 25, 37, 50, 75, 100]
PH_ATTR = {"spgf": "i_pspgf", "2psc": "i_p2psc", "2pgf": "i_p2pgf"}
app = get_app()
user = app.GetCurrentUser()
if app.GetActiveProject() is not None:
    app.GetActiveProject().Deactivate()


def one(name, cls):
    return app.GetCalcRelevantObjects("%s.%s" % (name, cls))[0]


def imax(el, side):
    return max(1000.0 * abs(attr(el, "m:Ikss:%s:%s" % (side, p), 0.0) or 0.0) for p in "ABC")


out = {}
for p in LEVELS:
    prj = user.GetContents("IEEE13 DG penetration %03d %%.IntPrj" % p)[0]
    prj.Activate()
    app.GetProjectFolder("study").GetContents(STUDY_CASE + ".IntCase", 1)[0].Activate()
    shc = app.GetFromStudyCase("ComShc")
    shc.SetAttribute("iopt_mde", 3)
    shc.SetAttribute("iopt_allbus", 0)
    r1, r2 = one("LOHL650-632", "ElmLne"), one("LOHL632-671end", "ElmLne")
    dgtr = one("2-Winding Transformer", "ElmTr2")
    terms = {t.loc_name: t for t in app.GetCalcRelevantObjects("*.ElmTerm")}
    rows = []
    for node in NODE_ORDER:
        for ft in ("LG", "LL", "LLG", "LLL"):
            for rf, tag in ((0.0, "max"), (3.0, "min")):
                if tag == "min" and ft != "LG":
                    continue
                seen = set()
                for idx in ([0] if ft == "LLL" else [0, 1, 2]):
                    code = PF_FAULT[ft]
                    shc.SetAttribute("shcobj", terms[node])
                    shc.SetAttribute("iopt_shc", code)
                    if code in PH_ATTR:
                        shc.SetAttribute(PH_ATTR[code], idx)
                    shc.SetAttribute("Rf", rf)
                    shc.SetAttribute("Xf", 0.0)
                    if shc.Execute() != 0:
                        continue
                    i_ph = [1000.0 * abs(attr(terms[node], "m:Ikss:" + ph, 0.0) or 0.0) for ph in "ABC"]
                    big = max(i_ph)
                    phases = "".join(ph for ph, i in zip("ABC", i_ph) if big > 0 and i > 0.2 * big)
                    if not phases or phases in seen or not set(phases) <= set(NODES[node]["phases"]):
                        continue
                    if ft != "LLL" and len(phases) != (1 if ft == "LG" else 2):
                        continue
                    seen.add(phases)
                    p_r2 = -(attr(r2, "m:Psum:bus2", 0.0) or 0.0)
                    rows.append(dict(node=node, type=ft, case=tag, phases=phases, I_fault=round(big, 1),
                                     I_R1=round(imax(r1, "bus1"), 1), I_R2=round(imax(r2, "bus2"), 1),
                                     R2_dir="fwd" if p_r2 >= 0 else "rev",
                                     I_DG=round(imax(dgtr, "bushv"), 1) if p else 0.0))
    out[p] = rows
    prj.Deactivate()
    print("%3d %%: %d faults" % (p, len(rows)), flush=True)

json.dump(out, open(os.path.join(HERE, "results", "sc_levels.json"), "w"), indent=1)
print("results/sc_levels.json written")
