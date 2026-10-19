"""
Step 4 - write the designed settings (results/settings.json) into PowerFactory and check that
PowerFactory's own relay and fuse models give the operating times used in step 3.

  python step4_apply_settings.py            # DSDR scheme (Fig. 17)   - left in the model
  python step4_apply_settings.py conventional   # conventional R2 (Fig. 14)

R2 units in the model:  "R2 Fast" / "R2 Delayed"        forward setting group (CT 1000/5)
                        "R2 Rev Fast" / "R2 Rev Delayed" reverse setting group (CT 500/5),
                                                         out of service in the conventional scheme
PowerFactory's library CDG34 is non-directional; the direction of each setting group is applied
in the coordination analysis (faults upstream of R2 = reverse, downstream = forward).
The check compares c:Ttrip of every unit and of the primary fuse with the Python curves.
"""

import csv
import json
import os
import sys

from pf_setup import activate, attr, out, obj, lib_type, RESULTS, clean_variation
from protection_data import FUSES, NODES
import step3_design_and_evaluate as S3

scheme = sys.argv[1] if len(sys.argv) > 1 else "dsdr"
settings = json.load(open(os.path.join(RESULTS, "settings.json")))[scheme]

app = activate(build=True)                 # settings belong to the base network
out("Applying the %s settings" % scheme)

for name, tname in settings["fuses"].items():
    f = obj(name, "RelFuse")
    f.typ_id = lib_type(tname + ".TypFuse", "ProtFuse")


def ct(cub, name, prim):
    hit = cub.GetContents(name + ".StaCt")
    c = hit[0] if hit else cub.CreateObject("StaCt", name)
    equip = app.GetProjectFolder("equip")
    tn = "CT %.0f-5A" % prim
    t = equip.GetContents(tn + ".TypCt")
    t = t[0] if t else equip.CreateObject("TypCt", tn)
    t.SetAttribute("primtaps", [prim])
    t.SetAttribute("sectaps", [5.0])
    c.typ_id = t
    c.SetAttribute("ptapset", prim)
    c.SetAttribute("stapset", 5.0)
    return c


def set_unit(name, tap, dial, ct_obj=None, in_service=True):
    r = obj(name, "ElmRelay")
    r.SetAttribute("outserv", 0 if in_service else 1)
    if ct_obj is not None:
        sl = list(r.GetAttribute("pdiselm"))
        sl[0] = ct_obj
        r.SetAttribute("pdiselm", sl)
    for toc in r.GetContents("*.RelToc"):
        if "Earth" in toc.loc_name:
            continue
        toc.SetAttribute("Ipsetr", tap)
        toc.SetAttribute("Tpset", dial)
    return r


r1 = settings["R1"]
set_unit("R1 Fast", r1["tap"], r1["tds_f"])
set_unit("R1 Delayed", r1["tap"], r1["tds_d"])
cub2 = obj("R2 Fast", "ElmRelay").GetParent()
fw = settings["R2fw"]
ct_fw = ct(cub2, "CT R2", fw["ct"])
set_unit("R2 Fast", fw["tap_f"], fw["tms_f"], ct_fw)
set_unit("R2 Delayed", fw["tap_d"], fw["tms_d"], ct_fw)
if "R2rv" in settings:
    rv = settings["R2rv"]
    ct_rv = ct(cub2, "CT R2 rev", rv["ct"])
    set_unit("R2 Rev Fast", rv["tap_f"], rv["tms_f"], ct_rv)
    set_unit("R2 Rev Delayed", rv["tap_d"], rv["tms_d"], ct_rv)
else:
    for u in ("R2 Rev Fast", "R2 Rev Delayed"):
        set_unit(u, 1.0, 0.1, None, in_service=False)
out("  R1 tap %.1f A (CT 900/5) TDS %.2f / %.2f" % (r1["tap"], r1["tds_f"], r1["tds_d"]))
out("  R2 forward plug %.1f / %.1f A (CT %.0f/5) TMS %.3f / %.3f" % (fw["tap_f"], fw["tap_d"], fw["ct"], fw["tms_f"], fw["tms_d"]))
if "R2rv" in settings:
    out("  R2 reverse plug %.1f / %.1f A (CT %.0f/5) TMS %.3f / %.3f" % (rv["tap_f"], rv["tap_d"], rv["ct"], rv["tms_f"], rv["tms_d"]))
out("  fuses: " + ", ".join("%s %s" % kv for kv in settings["fuses"].items()))

# ---- check PowerFactory's operating times against the Python curves ---------------------------
app = activate()                                   # study case with the substation transformer
shc = app.GetFromStudyCase("ComShc")
shc.SetAttribute("iopt_mde", 3)
terms = {t.loc_name: t for t in app.GetCalcRelevantObjects("*.ElmTerm")}
sym = app.GetCalcRelevantObjects("*.ElmSym")[0]
PH = {"spgf": "i_pspgf", "2psc": "i_p2psc", "2pgf": "i_p2pgf"}
UNITS = [("R1 Fast", "R1", "f"), ("R1 Delayed", "R1", "d"), ("R2 Fast", "R2fw", "f"), ("R2 Delayed", "R2fw", "d")]
if "R2rv" in settings:
    UNITS += [("R2 Rev Fast", "R2rv", "f"), ("R2 Rev Delayed", "R2rv", "d")]
s3 = dict(settings)


def pf_time(o):
    v = attr(o, "c:Ttrip")
    if v is None:
        return float("inf")
    v = v if isinstance(v, list) else [v]
    v = [x for x in v if x is not None and 0 < x < 9999]
    return min(v) if v else float("inf")


rows, worst = [], 0.0
for rec in [r for r in S3.FAULTS if r["case"] == "max" and r["dg"] in (0.0, 1.0) and r["where"] in NODES
            and not NODES[r["where"]].get("lv")]:
    sym.SetAttribute("outserv", 0 if rec["dg"] else 1)
    code = S3.D["faults"] and {"LG": "spgf", "LL": "2psc", "LLG": "2pgf", "LLL": "3rst"}[rec["type"]]
    shc.SetAttribute("shcobj", terms[rec["where"]])
    shc.SetAttribute("iopt_shc", code)
    if code in PH:
        shc.SetAttribute(PH[code], rec["index"])
    shc.SetAttribute("Rf", 0.0)
    shc.SetAttribute("Xf", 0.0)
    if shc.Execute() != 0:
        continue
    checks = []
    for unit, key, mode in UNITS:
        r = obj(unit, "ElmRelay")
        t_pf = min(pf_time(t) for t in r.GetContents("*.RelToc") if not attr(t, "outserv"))
        i = S3.imax(rec, "R1" if key == "R1" else "R2")
        t_py = S3.t_r1(i, s3, mode) if key == "R1" else S3.t_r2(i, s3, key, mode)
        checks.append((unit, t_pf, t_py))
    path = NODES[rec["where"]]["path"]
    if path:
        f = obj(path[0], "RelFuse")
        checks.append((path[0] + " MMT", pf_time(f), S3.FTYPE[settings["fuses"][path[0]]].mmt(S3.imax(rec, path[0]))))
    for unit, t_pf, t_py in checks:
        dev = 0.0 if t_pf == t_py else (abs(t_pf / t_py - 1) if t_py not in (0, float("inf")) else 1.0)
        if t_py < 100:
            worst = max(worst, dev)
        rows.append([rec["where"], rec["type"], rec["phases"], rec["dg"], unit, S3.fmt(t_pf, 4), S3.fmt(t_py, 4),
                     "%.2f" % (100 * dev) if dev < 1 else "-"])
sym.SetAttribute("outserv", 0)
clean_variation()
with open(os.path.join(RESULTS, "PF_vs_Python_times_%s.csv" % scheme), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["node", "fault", "phases", "DG", "device", "PowerFactory t (s)", "Python t (s)", "deviation %"])
    w.writerows(rows)
devs = sorted(float(r[7]) for r in rows if r[7] != "-")
out("Checked %d operating times: PowerFactory vs Python median deviation %.2f %%, max %.2f %%" % (
    len(rows), devs[len(devs) // 2], max(devs)))
bad = [r for r in rows if r[7] == "-" and r[5] != r[6]]
for r in bad[:10]:
    out("  trip / no-trip mismatch: %s" % r)
