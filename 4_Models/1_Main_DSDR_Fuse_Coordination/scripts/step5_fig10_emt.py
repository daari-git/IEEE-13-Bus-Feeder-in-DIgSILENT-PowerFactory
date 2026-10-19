"""
Step 5 - Fig. 10: time-domain fault current during the recloser's fast shots and the fuse operation.

Fault (paper): line-line a-c at 684 through 0.2 ohm, conventional settings (R2 forward).
Run twice in PowerFactory EMT: DG out (the paper's recloser-fuse sequence) and DG in.

Every switching time comes from the step-3 curves applied to the simulated currents
(one-cycle RMS of the EMT waveforms), in passes:
  pass 1  fault only                 -> R2 current -> R2 fast trip time
  pass 2  R2 fast, reclose, fast, reclose (dead time 0.3 s)
          -> F671-2 heating from its simulated current, including the DG current that keeps
             flowing while R2 is open: melts when sum(dt/MMT(I)) = 1, clears when sum(dt/TCT(I)) = 1
          -> R2 delayed trip (timer from the last reclose)
  pass 3  the whole sequence with the fuse opening (or R2 locking out if it is first)
PowerFactory's own relay and fuse elements are out of service during the runs (restored after).
"""

import csv
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pf_setup import activate, out, obj, RESULTS, clean_variation
import step3_design_and_evaluate as S3

T0, T_END, DT = 0.30, 2.00, 1e-4  # fault at 0.30 s, as in the paper's figure
T_BREAKER = 3 / 60.0              # recloser interrupting time
T_DEAD = 0.20                     # reclosing dead time read from the paper's figure (0.46 -> 0.65 s, 0.80 -> 1.00 s)
FAST_SHOTS = 2
CYCLE = 1 / 60.0

s = json.load(open(os.path.join(RESULTS, "settings.json")))["conventional"]
FIG10 = [r for r in S3.FAULTS if r["case"] == "Fig10"][0]
FUSE = S3.FTYPE[s["fuses"]["F671-2"]]

app = activate()
case = app.GetActiveStudyCase()
evts = case.GetContents("*.IntEvt")
evtfold = evts[0] if evts else app.GetFromStudyCase("IntEvt")   # a fresh project has no events folder yet
sym = app.GetCalcRelevantObjects("*.ElmSym")[0]
brk = obj("LOHL632-671end", "ElmLne").GetAttribute("bus2").GetContents("*.StaSwitch")[0]
fsw = obj("LOHL671-684", "ElmLne").GetAttribute("bus1").GetContents("*.StaSwitch")[0]
res = case.GetContents("Fig10 EMT.ElmRes")
res = res[0] if res else case.CreateObject("ElmRes", "Fig10 EMT")
for c in res.GetContents():
    c.Delete()
MON = [("I632in", obj("LOHL650-632", "ElmLne"), "bus2"),          # feeder current arriving at node 632 (paper's plot)
       ("I632", obj("LOHL632-671start", "ElmLne"), "bus1"),     # current leaving 632 towards 671
       ("IR2", obj("LOHL632-671end", "ElmLne"), "bus2"),
       ("IF", obj("LOHL671-684", "ElmLne"), "bus1")]              # through F671-2
for _, el, side in MON:
    for p in ("A", "C"):
        res.AddVariable(el, "m:I:%s:%s" % (side, p))


def simulate(events, tstop, csv_name):
    app.ResetCalculation()               # events cannot be edited while a simulation is initialised
    for e in evtfold.GetContents():
        e.Delete()
    sc = evtfold.CreateObject("EvtShc", "LL a-c at 684")
    sc.SetAttribute("p_target", obj("684", "ElmTerm"))
    sc.SetAttribute("time", T0)
    sc.SetAttribute("i_shc", 1)          # 2-phase
    sc.SetAttribute("i_p2psc", FIG10["index"])   # a-c (index found by the step-2 short circuit)
    sc.SetAttribute("R_f", 0.2)
    sc.SetAttribute("X_f", 0.0)
    for k, (tt, kind, label) in enumerate(events):
        ev = evtfold.CreateObject("EvtSwitch", "%02d %s" % (k, label))
        ev.SetAttribute("p_target", fsw if kind == "fuse" else brk)
        ev.SetAttribute("time", tt)
        ev.SetAttribute("i_switch", 1 if kind == "close" else 0)
        ev.SetAttribute("i_allph", 1)
    inc = app.GetFromStudyCase("ComInc")
    inc.SetAttribute("iopt_sim", "ins")
    inc.SetAttribute("dtemt", DT)
    inc.SetAttribute("p_resvar", res)
    sim = app.GetFromStudyCase("ComSim")
    sim.SetAttribute("tstop", tstop)
    if inc.Execute() or sim.Execute():
        raise RuntimeError("EMT simulation failed")
    path = os.path.join(RESULTS, csv_name)
    exp = case.CreateObject("ComRes", "export")
    exp.SetAttribute("pResult", res)
    exp.SetAttribute("iopt_exp", 6)
    exp.SetAttribute("f_name", path)
    exp.SetAttribute("iopt_sep", 0)
    exp.SetAttribute("col_Sep", ",")
    exp.SetAttribute("dec_Sep", ".")
    exp.Execute()
    exp.Delete()
    app.ResetCalculation()
    for e in evtfold.GetContents():
        e.Delete()
    with open(path) as f:
        rows = list(csv.reader(f))
    data = [[float(x) for x in r] for r in rows[2:] if r and r[0].strip()]
    t = [r[0] for r in data]
    wave = {}
    for key, el, _ in MON:                        # PowerFactory sorts the columns: map by name
        cols = [k for k in range(1, len(rows[0])) if rows[0][k] == el.loc_name]
        ca = [k for k in cols if "Phase Current A" in rows[1][k]][0]
        cc = [k for k in cols if "Phase Current C" in rows[1][k]][0]
        wave[key] = ([r[ca] for r in data], [r[cc] for r in data])
    return t, wave


def rms(t, x):
    """one-cycle moving RMS"""
    n = max(1, int(round(CYCLE / (t[1] - t[0]))))
    out_, acc = [], 0.0
    for k, v in enumerate(x):
        acc += v * v
        if k >= n:
            acc -= x[k - n] * x[k - n]
        out_.append(math.sqrt(max(acc, 0.0) / min(k + 1, n)))
    return out_


def i_max_rms(t, wave, key):
    a, c = rms(t, wave[key][0]), rms(t, wave[key][1])
    return [max(p, q) for p, q in zip(a, c)]


SUMMARY = {}


def run(dg_on):
    tag = "DG in" if dg_on else "DG out"
    sym.SetAttribute("outserv", 0 if dg_on else 1)
    # pass 1: R2 current -> fast trip time
    t, w = simulate([], T0 + 0.15, "Fig10_pass.csv")
    ir2 = i_max_rms(t, w, "IR2")
    i_r2 = max(v for tt, v in zip(t, ir2) if T0 + 0.05 < tt < T0 + 0.15)
    t_fast = S3.t_r2(i_r2, s, "R2fw", "f") + T_BREAKER
    events, tt = [], T0
    for shot in range(FAST_SHOTS):
        tt += t_fast
        events.append((tt, "open", "R2 fast trip %d" % (shot + 1)))
        tt += T_DEAD
        events.append((tt, "close", "R2 reclose %d" % (shot + 1)))
    t_last = tt
    # pass 2: fuse heating from the simulated fuse current
    t, w = simulate(events, T_END, "Fig10_pass.csv")
    iF = i_max_rms(t, w, "IF")
    ir2 = i_max_rms(t, w, "IR2")
    i_fault = max(v for tt_, v in zip(t, iF) if T0 < tt_ < T0 + t_fast)       # fuse current during the fault
    melt = clear = 0.0
    t_melt = t_clear = None
    how = "clears"
    t_delayed = None
    acc_d = 0.0
    for k in range(1, len(t)):
        dt = t[k] - t[k - 1]
        if t[k] < T0:
            continue
        i = iF[k]
        if i > 0:
            melt += dt / FUSE.mmt(i)
            clear += dt / FUSE.tct(i)
        if t_melt is None and melt >= 1:
            t_melt = t[k]
        if t_clear is None and clear >= 1:
            t_clear = t[k]
        # a fuse that has melted is finished as soon as a recloser interrupts its current
        if t_clear is None and t_melt is not None and t[k] > t_melt + CYCLE and i < 0.05 * i_fault:
            t_clear, how = t[k], "is blown (melted, current interrupted by R2)"
        if t[k] > t_last + 2 * CYCLE and t_delayed is None:       # R2 delayed timer after last reclose
            acc_d += dt / S3.t_r2(max(ir2[k], 1.0), s, "R2fw", "d")
            if acc_d >= 1:
                t_delayed = t[k] + T_BREAKER
    heat_fast = None
    for k in range(len(t)):
        if t[k] >= t_last:
            break
    melt_at_last = sum((t[j] - t[j - 1]) / FUSE.mmt(iF[j]) for j in range(1, len(t))
                       if T0 <= t[j] <= t_last and iF[j] > 0)
    if t_clear is not None and (t_delayed is None or t_clear < t_delayed):
        # the fault is gone after the fuse: no further recloser trips, only a pending reclose
        kept = [e for e in events if e[0] < t_clear]
        if kept and kept[-1][1] == "open":
            kept.append(events[len(kept)])
        events = sorted(kept + [(t_clear, "fuse", "F671-2 " + how.split(" (")[0])])
        final = "F671-2 %s at %.3f s" % (how, t_clear)
    elif t_delayed is not None:
        events.append((t_delayed, "open", "R2 lockout"))
        final = "R2 locks out at %.3f s" % t_delayed
    else:
        final = "no clearing within %.1f s" % T_END
    t, w = simulate(events, T_END, "Fig10_EMT_%s.csv" % tag.replace(" ", "_"))
    out("Fig. 10 %s: R2 %.0f A -> fast shot %.3f s incl. breaker; fuse heat at the end of the fast shots "
        "%.0f %% of melting; melts %s, %s" % (tag, i_r2, t_fast, 100 * melt_at_last,
                                              "at %.3f s" % t_melt if t_melt else "-", final))
    for e in events:
        out("   t = %.3f s  %s" % (e[0], e[2]))
    ra, rc = rms(t, w["I632in"][0]), rms(t, w["I632in"][1])

    def at(x, when):
        return x[min(range(len(t)), key=lambda j: abs(t[j] - when))]

    def peak(x, t1, t2):
        return max(abs(v) for tt_, v in zip(t, x) if t1 <= tt_ <= t2)
    node632 = dict(prefault_rms_a=at(ra, T0 - 0.002), prefault_rms_c=at(rc, T0 - 0.002),
                   fault_rms_a=at(ra, T0 + t_fast - 0.005), fault_rms_c=at(rc, T0 + t_fast - 0.005),
                   first_peak_a=peak(w["I632in"][0], T0, T0 + 0.03), first_peak_c=peak(w["I632in"][1], T0, T0 + 0.03),
                   steady_peak_a=peak(w["I632in"][0], T0 + 0.06, T0 + t_fast - 0.01),
                   steady_peak_c=peak(w["I632in"][1], T0 + 0.06, T0 + t_fast - 0.01),
                   dead_time_rms_a=at(ra, events[0][0] + T_DEAD - 0.02), dead_time_rms_c=at(rc, events[0][0] + T_DEAD - 0.02))
    out("   current into node 632 (A): prefault rms a/c %.0f / %.0f; fault rms a/c %.0f / %.0f, peak a/c %.0f / %.0f "
        "(first peak %.0f / %.0f); R2 open rms a/c %.0f / %.0f" % (
            node632["prefault_rms_a"], node632["prefault_rms_c"], node632["fault_rms_a"], node632["fault_rms_c"],
            node632["steady_peak_a"], node632["steady_peak_c"], node632["first_peak_a"], node632["first_peak_c"],
            node632["dead_time_rms_a"], node632["dead_time_rms_c"]))
    SUMMARY[tag] = dict(node632=node632, t_fault=T0, t_dead=T_DEAD, i_r2=i_r2, i_fuse=i_fault, t_fast=t_fast, heat_after_fast_shots=melt_at_last, t_melt=t_melt,
                        t_clear=t_clear, final=final, events=[(round(e[0], 3), e[2]) for e in events],
                        fuse=s["fuses"]["F671-2"], fast_shots_before_melt=sum(
                            1 for e in events if e[1] == "open" and (t_melt is None or e[0] <= t_melt)))
    return tag, t, w, events, melt_at_last, t_melt


# PowerFactory's own relay and fuse models would also act in the EMT run; the sequence is
# scripted from the curves instead, so they are taken out of service for the simulation.
PROT = [(o, o.GetAttribute("outserv")) for o in app.GetCalcRelevantObjects("*.ElmRelay") +
        app.GetCalcRelevantObjects("*.RelFuse")]
try:
    for o, _ in PROT:
        o.SetAttribute("outserv", 1)
    cases = [run(False), run(True)]
finally:
    app.ResetCalculation()
    for o, st in PROT:
        o.SetAttribute("outserv", st)
    sym.SetAttribute("outserv", 0)
    clean_variation()                  # the switching above was recorded in the variation stage
os.remove(os.path.join(RESULTS, "Fig10_pass.csv"))

fig, axes = plt.subplots(2, 1, figsize=(7.4, 6.2), sharex=True)
for ax, (tag, t, w, events, heat, t_melt) in zip(axes, cases):
    ax.plot(t, w["I632in"][1], lw=0.7, color="#d03b3b", label="phase c, feeder current at node 632")
    ax.plot(t, w["I632in"][0], lw=0.7, color="#2a78d6", label="phase a, feeder current at node 632")
    ax.plot(t, w["IF"][0], lw=0.6, color="#8a8983", alpha=0.75, label="phase a through fuse F671-2")
    top = max(max(map(abs, w["IF"][0])), max(map(abs, w["I632in"][0])), max(map(abs, w["I632in"][1])))
    for tt, kind, label in events:
        ax.axvline(tt, color="#52514e", lw=0.7, ls=":")
        ax.text(tt, top * 1.02, label, rotation=90, va="top", ha="right", fontsize=6.8, color="#52514e")
    ax.axvline(T0, color="#52514e", lw=0.8, ls="--")
    ax.text(T0, top * 1.02, "fault initiated", rotation=90, va="top", ha="right", fontsize=6.8, color="#52514e")
    if t_melt:
        ax.axvline(t_melt, color="#eb6834", lw=1.0, ls="--")
        ax.text(t_melt, -top * 1.02, "F671-2 melts", rotation=90, va="bottom", ha="right", fontsize=6.8,
                color="#eb6834")
    ax.set_ylim(-1.15 * top, 1.15 * top)
    ax.set_ylabel("Current (A)")
    ax.set_title("%s (fuse F671-2 %s)" % ("With DG" if tag == "DG in" else "Without DG", s["fuses"]["F671-2"].replace("A055C", "")), fontsize=9, loc="left")
    ax.grid(True, color="#d9d8d4", lw=0.5)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
axes[0].legend(frameon=False, fontsize=7.2, loc="lower left", ncol=3)
axes[1].set_xlabel("Time (s)")
fig.suptitle("Current at node 632, LL a-c fault at 684 through 0.2 ohm, PowerFactory EMT",
             fontsize=9.5, x=0.01, ha="left")
fig.tight_layout()
try:
    fig.savefig(os.path.join(RESULTS, "figures", "Fig10_EMT_LL_684.png"), dpi=160)
except OSError:                        # open in a viewer
    fig.savefig(os.path.join(RESULTS, "figures", "Fig10_EMT_LL_684_new.png"), dpi=160)
    out("NOTE: Fig10_EMT_LL_684.png is open in another program; the new figure is Fig10_EMT_LL_684_new.png")
json.dump(SUMMARY, open(os.path.join(RESULTS, "Fig10_summary.json"), "w"), indent=1)
out("Saved figures/Fig10_EMT_LL_684.png, results/Fig10_EMT_DG_*.csv and Fig10_summary.json")
