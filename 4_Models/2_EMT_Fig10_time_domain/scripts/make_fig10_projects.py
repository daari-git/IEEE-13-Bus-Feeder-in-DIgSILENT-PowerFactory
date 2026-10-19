"""
Fig. 10 (time-domain current at node 632, LL a-c fault at 684 through 0.2 ohm) in SEPARATE PowerFactory
projects, so that the replication project is not affected by the EMT events and the out-of-service
protection that this study needs.

  1. The user's Fig. 10 set-up in "IEEE13 DSDR Fuse Coordination" (study case "Study with Substation
     Transformer": short-circuit event, R2 switch events, fuse event, plot page "Curve plot") is copied to
       "IEEE13 Fig10 EMT - DG out"   (DG out of service)
       "IEEE13 Fig10 EMT - DG in"    (DG in service, switching times recalculated for the higher currents)
     In the copies the relays and fuses are out of service (the sequence is set by the events), the
     simulation is run and the copy is exported to pfd/.
  2. The replication project is then restored: events deleted, plot page emptied, relays, fuses and DG
     back in service (variation stage reset to its original objects).

Switching times = step5_fig10_emt.py (R2 fast curve and fuse heating from the simulated currents).
Output: pfd/*.pfd, results/Fig10_<case>.csv, results/Fig10_DG_out_and_in.png.  PowerFactory must be closed.
"""

import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "DSDR_Study"))
from pf_setup import get_app, attr, PROJECT, STUDY_CASE, clean_variation   # noqa: E402

RES, PFD = os.path.join(HERE, "results"), os.path.join(HERE, "pfd")
os.makedirs(RES, exist_ok=True)
os.makedirs(PFD, exist_ok=True)
EVENT_TIMES = {   # event name -> time (s)
    "DG out": {"LL a-c at 684 Rf 0.2": 0.300, "R2 fast trip 1": 0.420, "R2 reclose 1": 0.620, "R2 fast trip 2": 0.740,
               "R2 reclose 2": 0.940, "F671-2 clears": 1.613},
    "DG in": {"LL a-c at 684 Rf 0.2": 0.300, "R2 fast trip 1": 0.426, "R2 reclose 1": 0.626, "R2 fast trip 2": 0.753,
              "R2 reclose 2": 0.953, "F671-2 clears": 1.253},
}

app = get_app()
user = app.GetCurrentUser()
if app.GetActiveProject() is not None:
    app.GetActiveProject().Deactivate()
orig = user.GetContents(PROJECT + ".IntPrj")[0]


def activate(prj):
    prj.Activate()
    case = app.GetProjectFolder("study").GetContents(STUDY_CASE + ".IntCase", 1)[0]
    case.Activate()
    return case


def calc(name):
    return app.GetCalcRelevantObjects(name)


data = {}
for tag, times in EVENT_TIMES.items():
    name = "IEEE13 Fig10 EMT - %s" % tag
    for old in user.GetContents(name + ".IntPrj"):
        old.Delete()
    prj = user.AddCopy(orig, name)
    case = activate(prj)
    evf = case.GetContents("*.IntEvt")[0]
    events = {e.loc_name: e for e in evf.GetContents()}
    missing = set(times) - set(events)
    if missing:
        raise RuntimeError("events not found in the copied study case: %s" % missing)
    for n, t in times.items():
        events[n].SetAttribute("time", t)
    for o in calc("*.ElmRelay") + calc("*.RelFuse"):
        o.SetAttribute("outserv", 1)
    calc("Synchronous Machine.ElmSym")[0].SetAttribute("outserv", 0 if tag == "DG in" else 1)

    res = case.GetContents("Fig10 EMT.ElmRes")[0]
    inc, sim = app.GetFromStudyCase("ComInc"), app.GetFromStudyCase("ComSim")
    inc.SetAttribute("iopt_sim", "ins")
    inc.SetAttribute("dtemt", 1e-4)
    inc.SetAttribute("p_resvar", res)
    inc.SetAttribute("p_event", evf)
    sim.SetAttribute("tstop", 2.0)
    if inc.Execute() or sim.Execute():
        raise RuntimeError("EMT simulation failed (%s)" % tag)
    line = calc("LOHL650-632.ElmLne")[0]
    res.Load()
    ca, cc = res.FindColumn(line, "m:I:bus2:A"), res.FindColumn(line, "m:I:bus2:C")
    rows = [(res.GetValue(i, -1)[1], res.GetValue(i, ca)[1], res.GetValue(i, cc)[1]) for i in range(res.GetNumberOfRows())]
    res.Release()
    data[tag] = rows
    with open(os.path.join(RES, "Fig10_%s.csv" % tag.replace(" ", "_")), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["time (s)", "I phase a at 632 (A)", "I phase c at 632 (A)"])
        w.writerows(("%.5f" % t, "%.2f" % a, "%.2f" % c) for t, a, c in rows)
    prj.Deactivate()
    path = os.path.join(PFD, "IEEE13_Fig10_EMT_%s.pfd" % tag.replace(" ", "_"))
    if os.path.exists(path):
        os.remove(path)
    exp = user.CreateObject("CompfdExport", "export")
    exp.SetAttribute("g_objects", [prj])
    exp.SetAttribute("e:g_file", path)
    exp.Execute()
    exp.Delete()
    print("%s: %d samples, peak a/c %.0f / %.0f A; saved %s" % (tag, len(rows), max(abs(r[1]) for r in rows),
                                                              max(abs(r[2]) for r in rows), path if os.path.exists(path) else "-- EXPORT FAILED"))

# ---- restore the replication project ----------------------------------------------------------
case = activate(orig)
evf = case.GetContents("*.IntEvt")[0]
for e in evf.GetContents():
    e.Delete()
page = case.GetContents("*.SetDesktop", 1)[0].GetContents("Curve plot.GrpPage")
if page:
    ds = page[0].GetContents("*.PltLinebarplot")[0].GetContents("*.PltDataseries")[0]
    ds.ClearCurves()
n = clean_variation()
case = activate(orig)                 # re-read the network after the reset
prot = calc("*.ElmRelay") + calc("*.RelFuse")
sym = calc("Synchronous Machine.ElmSym")[0]
off = [o.loc_name for o in prot if attr(o, "outserv")]
print("replication project restored: %d records removed from the variation; relays/fuses out of service: %s; DG out of service: %s"
      % (n, off or "none", bool(attr(sym, "outserv"))))
orig.Deactivate()

# ---- figure -----------------------------------------------------------------------------------
fig, axes = plt.subplots(2, 1, figsize=(8, 6.2), sharex=True)
for ax, tag in zip(axes, ("DG out", "DG in")):
    t = [r[0] for r in data[tag]]
    ax.plot(t, [r[2] for r in data[tag]], color="#d03b3b", lw=0.7, label="phase c")
    ax.plot(t, [r[1] for r in data[tag]], color="#2a78d6", lw=0.7, label="phase a")
    for n, tt in EVENT_TIMES[tag].items():
        ax.axvline(tt, color="#55534e", lw=0.7, ls=":")
        ax.text(tt, 5800, n, rotation=90, va="top", ha="right", fontsize=6.8, color="#55534e")
    ax.set_ylim(-6000, 6000)
    ax.set_ylabel("Current at 632 (A)")
    ax.set_title("%s (PowerFactory EMT, project 'IEEE13 Fig10 EMT - %s')" % (tag, tag), fontsize=9, loc="left")
    ax.grid(True, color="#d9d8d4", lw=0.5)
axes[0].legend(fontsize=8, frameon=False, loc="lower left", ncol=2)
axes[1].set_xlabel("Time (s)")
fig.suptitle("Fig. 10 - current at node 632, LL a-c fault at 684 through 0.2 ohm", fontsize=10, x=0.01, ha="left")
fig.tight_layout()
fig.savefig(os.path.join(RES, "Fig10_DG_out_and_in.png"), dpi=160)
print("results/Fig10_DG_out_and_in.png written")
