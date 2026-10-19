"""
Audit of the PowerFactory model against the results of the pipeline (read-only except for switching the
DG for the comparison, which is undone at the end).  Run with PowerFactory closed.

Checks
  A  projects present
  B  network variation "Substation Transformer" holds only its 13 original objects
  C  no simulation events left in the study cases used by the pipeline
  D  relay units: in service, tap, dial and CT as in settings.json (DSDR, the state run_all leaves)
  E  fuses: in service, size as in settings.json, at the location given in protection_data.py
  F  DG: in service, Table I data, rating, operating point, step-up transformer
  G  load flow (DG out / in): every measured current against studies.json
  H  every bolted fault of studies.json (DG out / in) re-run: currents through R1, R2, fuses, branches
Writes results/Model_audit.txt.
"""

import json
import os

from pf_setup import get_app, attr, PROJECT, STUDY_CASE, BUILD_CASE, RESULTS, _ORIGINAL_STAGE, clean_variation
from protection_data import FUSES, RECLOSERS, TABLE2_BRANCHES, PF_FAULT

app = get_app()
user = app.GetCurrentUser()
if app.GetActiveProject() is not None:
    app.GetActiveProject().Deactivate()
D = json.load(open(os.path.join(RESULTS, "studies.json")))
S = json.load(open(os.path.join(RESULTS, "settings.json")))["dsdr"]
T1 = json.load(open(os.path.join(RESULTS, "Table_I_model.json")))
lines, problems = [], []


def say(t=""):
    lines.append(t)
    print(t, flush=True)


def bad(t):
    problems.append(t)
    say("   !! " + t)


# ---- A ------------------------------------------------------------------------------------------
say("A. Projects: " + ", ".join(p.loc_name for p in user.GetContents("*.IntPrj")))
prj = user.GetContents(PROJECT + ".IntPrj")[0]
prj.Activate()
cases = {c.loc_name: c for c in app.GetProjectFolder("study").GetContents("*.IntCase", 1)}
cases[STUDY_CASE].Activate()

# ---- B ------------------------------------------------------------------------------------------
for st in prj.GetContents("*.IntSstage", 1):
    keep = _ORIGINAL_STAGE.get(st.loc_name)
    if keep is None:
        continue
    extra = sorted(o.loc_name for o in st.GetContents() if o.loc_name not in keep)
    say("B. Variation stage '%s': %d objects%s" % (st.loc_name, len(st.GetContents()), "" if not extra else ", extra: %s" % extra))
    if extra:
        bad("variation stage holds changes made in the study case: %s" % extra)

# ---- C ------------------------------------------------------------------------------------------
for name in (STUDY_CASE, BUILD_CASE):
    allev = [e for f in cases[name].GetContents("*.IntEvt") for e in f.GetContents()]
    # the DIgSILENT example .pfd itself contains one short-circuit event without a target (t = 5.1 s) in
    # 'Study Detailed Network Model'; it is inert and present in the untouched import as well
    evs = [e.loc_name for e in allev if attr(e, "p_target") is not None]
    say("C. Events in '%s': %s%s" % (name, evs or "none", " (plus %d without target, from the original .pfd)" % (len(allev) - len(evs))
                                     if len(allev) > len(evs) else ""))
    if evs:
        bad("events left in study case '%s': %s" % (name, evs))


def one(n, c):
    hits = app.GetCalcRelevantObjects("%s.%s" % (n, c))
    return hits[0] if hits else None


# ---- D ------------------------------------------------------------------------------------------
UNITS = {"R1 Fast": ("R1", "tap", "tds_f", None), "R1 Delayed": ("R1", "tap", "tds_d", None),
         "R2 Fast": ("R2fw", "tap_f", "tms_f", "ct"), "R2 Delayed": ("R2fw", "tap_d", "tms_d", "ct"),
         "R2 Rev Fast": ("R2rv", "tap_f", "tms_f", "ct"), "R2 Rev Delayed": ("R2rv", "tap_d", "tms_d", "ct")}
say("D. Relay units (expected = settings.json, DSDR)")
for unit, (grp, tk, dk, ctk) in UNITS.items():
    r = one(unit, "ElmRelay")
    if r is None:
        bad("relay unit %s missing" % unit)
        continue
    tocs = [t for t in r.GetContents("*.RelToc") if "Earth" not in t.loc_name and not attr(t, "outserv")]
    tap, dial = (attr(tocs[0], "Ipsetr"), attr(tocs[0], "Tpset")) if tocs else (None, None)
    ct = attr(r.GetAttribute("pdiselm")[0], "ptapset") if r.GetAttribute("pdiselm") and r.GetAttribute("pdiselm")[0] else None
    exp_tap, exp_dial = S[grp][tk], S[grp][dk]
    exp_ct = S[grp]["ct"] if ctk else S["R1"]["ct"]
    ok = (not attr(r, "outserv") and tap is not None and abs(tap - exp_tap) < 1e-6 and abs(dial - exp_dial) < 1e-6
          and (ct is None or abs(ct - exp_ct) < 1e-6))
    say("   %-15s %s  tap %s (exp %s)  dial %s (exp %s)  CT %s/5 (exp %s/5)" % (
        unit, "in service" if not attr(r, "outserv") else "OUT OF SERVICE", tap, exp_tap, dial, exp_dial, ct, exp_ct))
    if not ok:
        bad("relay unit %s differs from settings.json" % unit)

# ---- E ------------------------------------------------------------------------------------------
say("E. Fuses (expected size = settings.json, DSDR)")
for name, (loc, _, _) in FUSES.items():
    f = one(name, "RelFuse")
    if f is None:
        bad("fuse %s missing" % name)
        continue
    cub = f.GetParent()
    branch = attr(cub, "obj_id")
    at = branch.loc_name if branch else "?"
    exp_at = loc[1]
    t = f.typ_id.loc_name if f.typ_id else None
    ok = not attr(f, "outserv") and t == S["fuses"][name] and at == exp_at
    say("   %-7s %-11s (exp %-11s) at %-15s (exp %-15s) %s" % (name, t, S["fuses"][name], at, exp_at,
                                                            "in service" if not attr(f, "outserv") else "OUT OF SERVICE"))
    if not ok:
        bad("fuse %s differs" % name)

# ---- F ------------------------------------------------------------------------------------------
sym, tr = one("Synchronous Machine", "ElmSym"), one("2-Winding Transformer", "ElmTr2")
typ = sym.typ_id
diff = {k: (round(attr(typ, k), 4), v) for k, v in T1.items() if k in ("xl", "rstr", "xd", "xq", "xds", "xqs", "xdss", "xqss",
                                                                     "tds0", "tdss0", "tqs0", "tqss0", "h", "sgn", "ugn", "iturbo")
        and abs((attr(typ, k) or 0) - v) > 1e-3}
say("F. DG: %s, %.2f MVA, P %.2f MW, Q %.2f Mvar, transformer %.2f MVA uk %.1f %%; Table I %s" % (
    "in service" if not attr(sym, "outserv") else "OUT OF SERVICE", attr(typ, "sgn"), attr(sym, "pgini"), attr(sym, "qgini"),
    attr(tr.typ_id, "strn"), attr(tr.typ_id, "uktr"), "as recorded" if not diff else "DIFFERS %s" % diff))
if attr(sym, "outserv") or diff or abs(attr(typ, "sgn") - 4.05) > 1e-3 or abs(attr(sym, "pgini") - 3.24) > 1e-3:
    bad("DG differs from the replication")

# ---- G / H: calculations against studies.json ---------------------------------------------------
POINTS = {k: tuple(v) for k, v in D["points"].items()}


def element(loc):
    if loc[0] == "load":
        return one(loc[1], "ElmLod"), "bus1"
    for cls in ("ElmLne", "ElmTr2", "ElmCoup"):
        e = one(loc[1], cls)
        if e is not None:
            return e, loc[2]


EL = {k: element(v) for k, v in POINTS.items()}
TERMS = {t.loc_name: t for t in app.GetCalcRelevantObjects("*.ElmTerm")}


def currents(var, scale):
    return {k: max(scale * abs(attr(e, "%s:%s:%s" % (var, side, p), 0.0) or 0.0) for p in "ABC") for k, (e, side) in EL.items()}


ldf, shc = app.GetFromStudyCase("ComLdf"), app.GetFromStudyCase("ComShc")
ldf.SetAttribute("iopt_net", 1)
shc.SetAttribute("iopt_mde", 3)
shc.SetAttribute("iopt_allbus", 0)
dg_state = attr(sym, "outserv")
worst_lf, worst_sc, n_sc, big = 0.0, 0.0, 0, []
for dg in (0, 1):
    sym.SetAttribute("outserv", 0 if dg else 1)
    ldf.Execute()
    now = currents("m:I", 1.0)
    ref = D["loadflow"]["dg_in" if dg else "dg_out"]
    for k in now:
        r = max(ref[k])
        if r > 1.0:
            dv = abs(now[k] / r - 1)
            worst_lf = max(worst_lf, dv)
            if dv > 0.005:
                big.append("load flow DG %s, %s: %.1f A now, %.1f A in studies.json" % ("in" if dg else "out", k, now[k], r))
    for rec in [r for r in D["faults"] if r["case"] == "max" and r["dg"] == float(dg) and r["dist"] is None]:
        code = PF_FAULT[rec["type"]]
        shc.SetAttribute("shcobj", TERMS[rec["where"]])
        shc.SetAttribute("iopt_shc", code)
        if code in ("spgf", "2psc", "2pgf"):
            shc.SetAttribute({"spgf": "i_pspgf", "2psc": "i_p2psc", "2pgf": "i_p2pgf"}[code], rec["index"])
        shc.SetAttribute("Rf", 0.0)
        shc.SetAttribute("Xf", 0.0)
        if shc.Execute():
            big.append("fault %s %s %s no longer calculates" % (rec["where"], rec["type"], rec["phases"]))
            continue
        now = currents("m:Ikss", 1000.0)
        n_sc += 1
        for k in now:
            r = max(rec["I"][k])
            if r > 5.0:
                dv = abs(now[k] / r - 1)
                worst_sc = max(worst_sc, dv)
                if dv > 0.005:
                    big.append("fault %s %s %s DG %s, %s: %.0f A now, %.0f A in studies.json" % (
                        rec["where"], rec["type"], rec["phases"], "in" if dg else "out", k, now[k], r))
sym.SetAttribute("outserv", dg_state)
say("G. Load flow DG out / in: largest deviation from studies.json %.3f %%" % (100 * worst_lf))
say("H. %d bolted faults re-run (DG out and in): largest deviation from studies.json %.3f %%" % (n_sc, 100 * worst_sc))
for b in big[:20]:
    bad(b)
clean_variation()                      # undo the DG switching recorded in the variation
prj.Deactivate()

say("\nRESULT: " + ("model matches the pipeline's results - nothing missing or changed" if not problems
                    else "%d problem(s) found, listed above" % len(problems)))
with open(os.path.join(RESULTS, "Model_audit.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
