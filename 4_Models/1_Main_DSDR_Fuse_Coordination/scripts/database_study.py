"""
Load-flow and short-circuit database of the IEEE 13-node feeder, to be established and checked
BEFORE any relay coordination (no pickup, time dial, curve or fuse is changed by this script).

  Case A  DG disconnected          Case B  DG connected (4.05 MVA at 692, data of the model)
  1 / 2   load flow: current, sign, direction, P, Q at R1 and R2
  3 / 4   bus voltages (kV, pu, angle) per phase
  5 / 6   short circuits at every bus: every fault type and phase combination that exists there
          (bolted), and LG through 3 ohm; fault current, current through R1 and R2 with sign

Sign convention: + = forward, - = reverse.  Forward is away from the grid along the feeder:
  R1  at RG60 on line RG60-632   forward = RG60 -> 632
  R2  at 671 on line 632-671     forward = 632 -> 671
The convention is checked against the model (relay cubicle, element, distance from the grid).

Direction of a load-flow current: sign of the active power in the forward reference.
Direction of a fault current: positive-sequence current in the forward reference against the
pre-fault positive-sequence voltage at the relay (a memory-polarised directional element with a
45 deg characteristic angle: forward when the current lies between 135 deg lagging and 45 deg leading).

If,max  largest phase current at the faulted bus over the fault types that exist there (bolted).
If,min  LG fault through 3 ohm at the farthest node of each protection section (paper, Sec. IV-A);
        farthest = largest line length from the section's device, from the model's line lengths.

Outputs: results/database/*.csv and results/database/Database_Report.txt (also printed).
"""

import cmath
import csv
import math
import os

import pf_setup
from pf_setup import activate, attr, obj, RESULTS, dg_units, clean_variation
from protection_data import NODE_ORDER, PF_FAULT, TABLE2_BRANCHES, RECLOSERS, OLF

out = pf_setup.out
OUT = os.path.join(RESULTS, "database")
os.makedirs(OUT, exist_ok=True)
REPORT = []

BUSES = ["650", "RG60"] + NODE_ORDER + ["DG"]                # voltage tables
UPSTREAM_OF_R2 = ["632", "633", "634", "645", "646", "DL"]   # paper: R2 reverse with DG
DOWNSTREAM_OF_R2 = ["671", "692", "675", "680", "684", "611", "652"]
FAULT_TYPES = ["LLL", "LLG", "LL", "LG"]
PH_ATTR = {"spgf": "i_pspgf", "2psc": "i_p2psc", "2pgf": "i_p2pgf"}
RF_MIN = 3.0                                                 # ohm, If,min (paper)
RCA = 45.0                                                   # deg, directional characteristic angle
SIDES = ("bus1", "bus2", "bushv", "buslv")
A_OP = complex(-0.5, math.sqrt(3) / 2)

app = activate()
ldf = app.GetFromStudyCase("ComLdf")
shc = app.GetFromStudyCase("ComShc")
TERMS = {t.loc_name: t for t in app.GetCalcRelevantObjects("*.ElmTerm")}
sym = dg_units()[0]


# ---------------------------------------------------------------------------------------------
# report helpers
# ---------------------------------------------------------------------------------------------
def say(s=""):
    REPORT.append(s)
    out(s)


def heading(s):
    say("")
    say("=" * 110)
    say(s)
    say("=" * 110)


def table(head, rows, name=None):
    """Aligned text table in the report; the same rows as CSV when a file name is given."""
    rows = [[("" if c is None else c if isinstance(c, str) else "%g" % c) for c in r] for r in rows]
    w = [max(len(str(x)) for x in col) for col in zip(head, *rows)] if rows else [len(h) for h in head]
    line = lambda r: "  " + " | ".join(str(c).ljust(n) for c, n in zip(r, w))
    say(line(head))
    say("  " + "-+-".join("-" * n for n in w))
    for r in rows:
        say(line(r))
    if name:
        with open(os.path.join(OUT, name), "w", newline="") as f:
            wr = csv.writer(f)
            wr.writerow(head)
            wr.writerows(rows)


def f1(x):
    return "%.1f" % x


def signed(mag, sign):
    return "0.0" if sign == 0 else "%s%.1f" % ("+" if sign > 0 else "-", mag)


WORD = {1: "forward", -1: "reverse", 0: "no current"}
SIGN = {1: "+", -1: "-", 0: "0"}


# ---------------------------------------------------------------------------------------------
# network: connectivity, distances from the grid, phases present
# ---------------------------------------------------------------------------------------------
def element(loc):
    for cls in ("ElmLne", "ElmTr2", "ElmCoup"):
        hits = app.GetCalcRelevantObjects("%s.%s" % (loc[1], cls))
        if hits:
            return hits[0], loc[2]
    raise KeyError(loc)


def term_of(el, side):
    return attr(attr(el, side), "cterm").loc_name


EDGES = {}                                            # terminal -> [(terminal, length)]
for cls in ("ElmLne", "ElmTr2", "ElmCoup"):
    for o in app.GetCalcRelevantObjects("*." + cls):
        ends = [term_of(o, s) for s in SIDES if attr(o, s) is not None]
        if len(ends) == 2:
            d = attr(o, "dline", 0.0) if cls == "ElmLne" else 0.0
            EDGES.setdefault(ends[0], []).append((ends[1], d))
            EDGES.setdefault(ends[1], []).append((ends[0], d))


def distances(start):
    dist, todo = {start: 0.0}, [start]
    while todo:
        a = todo.pop()
        for b, d in EDGES.get(a, []):
            if b not in dist or dist[a] + d < dist[b] - 1e-9:
                dist[b] = dist[a] + d
                todo.append(b)
    return dist


GRID = app.GetCalcRelevantObjects("*.ElmXnet")[0]
FROM_GRID = distances(term_of(GRID, "bus1"))

DEV = {}
for name, cfg in RECLOSERS.items():
    el, side = element(cfg["loc"])
    other = [s for s in SIDES if attr(el, s) is not None and s != side][0]
    here, there = term_of(el, side), term_of(el, other)
    relays = [r.loc_name for r in attr(el, side).GetContents("*.ElmRelay")]
    # PowerFactory counts a current positive when it flows from the terminal into the element.
    # Forward (away from the grid) is into the element when the relay sits at the element's grid end.
    fwd = 1 if FROM_GRID[here] < FROM_GRID[there] else -1
    DEV[name] = dict(el=el, side=side, term=here, other=there, fwd=fwd, relays=relays)

SECTION = {"%s-%s" % (frm, to): (element(("line", br, side)), nodes) for frm, to, br, side, nodes in TABLE2_BRANCHES}


def phases_present(node):
    return "".join(p for p in "ABC" if (attr(TERMS[node], "m:u:" + p, 0.0) or 0.0) > 0.01)


# ---------------------------------------------------------------------------------------------
# protection settings must not change
# ---------------------------------------------------------------------------------------------
def protection_snapshot():
    snap = {}
    for r in app.GetCalcRelevantObjects("*.ElmRelay"):
        snap[r.loc_name] = (attr(r, "outserv"),) + tuple(
            (t.loc_name, attr(t, "Ipsetr"), attr(t, "Tpset"), attr(t, "outserv"), attr(attr(t, "pcharac"), "loc_name"))
            for t in r.GetContents("*.RelToc"))
    for f in app.GetCalcRelevantObjects("*.RelFuse"):
        snap[f.loc_name] = attr(attr(f, "typ_id"), "loc_name")
    return snap


# ---------------------------------------------------------------------------------------------
# measurements
# ---------------------------------------------------------------------------------------------
def phasors(el, side, var, scale):
    return [cmath.rect(scale * (attr(el, "%s:%s:%s" % (var, side, p), 0.0) or 0.0),
                       math.radians(attr(el, "m:phii:%s:%s" % (side, p), 0.0) or 0.0)) for p in "ABC"]


def pos_seq(ph):
    return (ph[0] + A_OP * ph[1] + A_OP * A_OP * ph[2]) / 3.0


def v1_at(term):
    t = TERMS[term]
    return pos_seq([cmath.rect(attr(t, "m:U:" + p, 0.0) or 0.0, math.radians(attr(t, "m:phiu:" + p, 0.0) or 0.0))
                    for p in "ABC"])


def loadflow(dg_on):
    sym.SetAttribute("outserv", 0 if dg_on else 1)
    if ldf.Execute() != 0:
        raise RuntimeError("load flow failed (DG %s)" % ("in" if dg_on else "out"))
    res = {"dev": {}, "bus": {}, "v1": {}}
    for name, d in DEV.items():
        el, side, k = d["el"], d["side"], d["fwd"]
        i = [attr(el, "m:I:%s:%s" % (side, p), 0.0) or 0.0 for p in "ABC"]
        pp = [k * (attr(el, "m:P:%s:%s" % (side, p), 0.0) or 0.0) for p in "ABC"]
        psum, qsum = k * attr(el, "m:Psum:" + side, 0.0), k * attr(el, "m:Qsum:" + side, 0.0)
        res["dev"][name] = dict(I=i, P_ph=pp, P=psum, Q=qsum, sign=1 if psum > 0 else -1,
                                sign_ph=[1 if x > 0 else -1 for x in pp],
                                u=[attr(TERMS[d["term"]], "m:u:" + p, 0.0) or 0.0 for p in "ABC"])
        res["v1"][name] = v1_at(d["term"])
    for b in BUSES:
        t = TERMS[b]
        res["bus"][b] = {p: (attr(t, "m:U:" + p), attr(t, "m:u:" + p), attr(t, "m:phiu:" + p)) for p in "ABC"
                         if (attr(t, "m:u:" + p, 0.0) or 0.0) > 0.01}
    return res


def run_fault(node, ftype, index, rf, v1pre):
    code = PF_FAULT[ftype]
    shc.SetAttribute("iopt_mde", 3)                    # complete method (pre-fault load flow)
    shc.SetAttribute("iopt_allbus", 0)
    shc.SetAttribute("shcobj", TERMS[node])
    shc.SetAttribute("iopt_shc", code)
    if code in PH_ATTR:
        shc.SetAttribute(PH_ATTR[code], index)
    shc.SetAttribute("Rf", rf)
    shc.SetAttribute("Xf", 0.0)
    if shc.Execute() != 0:
        return None
    ifault = [1000.0 * abs(attr(TERMS[node], "m:Ikss:" + p, 0.0) or 0.0) for p in "ABC"]
    big = max(ifault)
    if big <= 0:
        return None
    rec = dict(node=node, type=ftype, rf=rf, ifault=ifault,
               phases="".join(p for p, i in zip("ABC", ifault) if i > 0.2 * big), dev={}, sec={})
    for name, d in DEV.items():
        ph = [d["fwd"] * x for x in phasors(d["el"], d["side"], "m:Ikss", 1000.0)]
        mag, i1 = max(abs(x) for x in ph), pos_seq(ph)
        if mag < 1.0:
            sign, ang = 0, None
        else:
            ang = math.degrees(cmath.phase(i1 / v1pre[name]))
            sign = 1 if math.cos(math.radians(ang + RCA)) > 0 else -1
        rec["dev"][name] = dict(I=[abs(x) for x in ph], mag=mag, sign=sign, ang=ang)
    for key, ((el, side), _) in SECTION.items():
        rec["sec"][key] = max(abs(x) for x in phasors(el, side, "m:Ikss", 1000.0))
    return rec


def sweep(v1pre, present):
    """Every fault that exists at every bus (bolted), and LG through 3 ohm on every phase."""
    res, missing = [], {}
    for node in NODE_ORDER:
        for ft, rf in [(t, 0.0) for t in FAULT_TYPES] + [("LG", RF_MIN)]:
            need = {"LLL": 3, "LLG": 2, "LL": 2, "LG": 1}[ft]
            if len(present[node]) < need:
                missing.setdefault(node, []).append(ft)
                continue
            seen = set()
            for idx in ([0] if ft == "LLL" else [0, 1, 2]):
                r = run_fault(node, ft, idx, rf, v1pre)
                if r is None or len(r["phases"]) != need or r["phases"] in seen:
                    continue
                if not set(r["phases"]) <= set(present[node]):
                    continue
                seen.add(r["phases"])
                res.append(r)
    return res, missing


# ---------------------------------------------------------------------------------------------
# the study
# ---------------------------------------------------------------------------------------------
def fault_rows(recs):
    rows = []
    for r in recs:
        d1, d2 = r["dev"]["R1"], r["dev"]["R2"]
        rows.append([r["node"], r["type"], r["phases"], "%g" % r["rf"], f1(max(r["ifault"])),
                     f1(d1["mag"]), SIGN[d1["sign"]], WORD[d1["sign"]],
                     f1(d2["mag"]), SIGN[d2["sign"]], WORD[d2["sign"]]])
    return rows


def ifmax(recs, node):
    cand = [r for r in recs if r["node"] == node and r["rf"] == 0.0]
    return max(cand, key=lambda r: max(r["ifault"]))


def ifmin_rows(recs):
    rows = []
    for key, ((el, side), nodes) in SECTION.items():
        dist = distances(term_of(el, side))
        far = max(nodes, key=lambda n: dist[n])
        lg = [r for r in recs if r["rf"] == RF_MIN and r["node"] in nodes]
        at_far = min((r for r in lg if r["node"] == far), key=lambda r: r["sec"][key])
        low = min(lg, key=lambda r: r["sec"][key])
        rows.append(dict(section=key, far=far, dist=dist[far], phase=at_far["phases"], ifault=max(at_far["ifault"]),
                         isec=at_far["sec"][key], low_node=low["node"], low_phase=low["phases"], low=low["sec"][key]))
    return rows


def main():
    checks = []

    def check(ok, text):
        checks.append(("PASS" if ok else "CHECK", text))

    before = protection_snapshot()
    dg_state = sym.GetAttribute("outserv")

    # ---- preconditions ------------------------------------------------------------------------
    heading("0. MODEL, REFERENCE DIRECTIONS AND OPEN POINTS (before any calculation)")
    say("Project: %s   Study case: %s" % (app.GetActiveProject().loc_name, app.GetActiveStudyCase().loc_name))
    say("Load flow: AC unbalanced, 3-phase (ABC).  Short circuit: complete method (pre-fault load flow), "
        "initial symmetrical current Ikss.")
    closed = []
    for name, d in DEV.items():
        for sw in attr(d["el"], d["side"]).GetContents("*.StaSwitch"):
            if attr(sw, "on_off") == 0:
                sw.SetAttribute("on_off", 1)
                closed.append(name)
    for name in closed:
        say("NOTE: the breaker of %s was OPEN in the model and has been closed. With it open the feeder behind it is "
            "an island and no load flow or short circuit there is valid." % name)
    say("")
    say("Reference direction of the reclosers (+ = forward = away from the grid):")
    table(["Device", "Relay units in the model", "Relay terminal", "Measured element", "Forward =", "Line distance from the grid"],
          [[n, ", ".join(d["relays"]), d["term"], d["el"].loc_name,
            "%s -> %s" % ((d["term"], d["other"]) if d["fwd"] > 0 else (d["other"], d["term"])),
            "%.0f (relay end) / %.0f (other end)" % (FROM_GRID[d["term"]], FROM_GRID[d["other"]])] for n, d in DEV.items()])
    say("R2 sits at the 671 end of line 632-671. PowerFactory counts current positive from the terminal into the "
        "element, i.e. 671 -> 632 for R2, so R2's PowerFactory values are multiplied by -1 to get the forward "
        "reference 632 -> 671. R1's values are used as they are.")
    for n, d in DEV.items():
        check(bool(d["relays"]), "%s: relay units found in the cubicle at %s of %s; forward = away from the grid" % (
            n, d["term"], d["el"].loc_name))

    typ = sym.typ_id
    tr = obj("2-Winding Transformer", "ElmTr2")
    sub = obj("TrSubstation", "ElmTr2")
    say("")
    say("DG and transformer data as found in the model:")
    say("  DG: synchronous, %.2f MVA / %.2f kV at node %s through a %.2f/%.2f kV transformer, uk = %.0f %% (%s)" % (
        attr(typ, "sgn"), attr(typ, "ugn"), term_of(tr, "bushv"), attr(tr.typ_id, "utrn_h"), attr(tr.typ_id, "utrn_l"),
        attr(tr.typ_id, "uktr"), attr(tr.typ_id, "vecgrp")))
    say("  Table I: xd %.3f, xq %.3f, xd' %.3f, xq' %.3f, xd'' %.3f, xq'' %.3f, xl %.3f, rstr %.4f pu" % tuple(
        attr(typ, k, float("nan")) for k in ("xd", "xq", "xds", "xqs", "xdss", "xqss", "xl", "rstr")))
    say("Modelling choices - values not fixed by the method, with what the model uses:")
    say("  1. Source impedance. Model: %s, Sk'' = %.0f MVA, behind the %.0f MVA "
        "%.0f/%.2f kV substation transformer, uk = %.2f %% (IEEE 13-node benchmark data)." % (
            GRID.loc_name, attr(GRID, "snss"), attr(sub.typ_id, "strn"), attr(sub.typ_id, "utrn_h"),
            attr(sub.typ_id, "utrn_l"), attr(sub.typ_id, "uktr")))
    say("  2. DG operating point for the load flow. Model: P = %.2f MW, voltage control (%s) at "
        "%.2f pu; Q follows from the load flow." % (attr(sym, "pgini"), attr(sym, "av_mode"), attr(sym, "usetp")))
    say("  3. Relay / CT reference direction: defined above from the use of R2 "
        "(forward for faults at 671 and beyond).")
    say("  4. Short-circuit method: complete method (pre-fault load flow).")
    say("  5. 'Farthest node' of each protection section: taken from the model's line lengths.")
    say("  6. Fault location in the upstream section 632-671: the distributed-load lateral 'DL' at the middle of the line.")
    say("  7. Regulator taps (fixed, from the model): %s." % ", ".join(
        "%s %+d" % (o.loc_name, attr(o, "nntap")) for o in app.GetCalcRelevantObjects("Vreg*.ElmTr2")))

    # ---- load flows ---------------------------------------------------------------------------
    lf = {0: loadflow(False)}
    present = {n: phases_present(n) for n in NODE_ORDER}
    sc, missing = {}, {}
    sc[0], missing = sweep(lf[0]["v1"], present)
    lf[1] = loadflow(True)
    sc[1], _ = sweep(lf[1]["v1"], present)

    for dg, step, case in ((0, 1, "CASE A - DG DISCONNECTED"), (1, 2, "CASE B - DG CONNECTED")):
        heading("%d. LOAD FLOW %s  (%s)" % (step, "WITHOUT DG" if dg == 0 else "WITH DG", case))
        rows = []
        for n in DEV:
            r = lf[dg]["dev"][n]
            rows.append([n, signed(max(r["I"]), r["sign"]), SIGN[r["sign"]], WORD[r["sign"]], "%.1f" % r["P"], "%.1f" % r["Q"],
                         " / ".join(signed(i, s) for i, s in zip(r["I"], r["sign_ph"])),
                         " / ".join("%.1f" % x for x in r["P_ph"]), " / ".join("%.4f" % x for x in r["u"])])
        table(["Device", "Current (A)", "Sign", "Direction", "P (kW)", "Q (kvar)", "I per phase A / B / C (A)",
               "P per phase (kW)", "Voltage at the relay (pu)"], rows, "%d_LoadFlow_DG_%s.csv" % (step, "in" if dg else "out"))
        say("Current = largest phase current; its sign and the direction follow the total active power in the "
            "forward reference. P and Q are positive in the forward direction.")
        for n in DEV:
            r = lf[dg]["dev"][n]
            odd = [p for p, s_ in zip("ABC", r["sign_ph"]) if s_ != r["sign"]]
            if odd:
                say("NOTE: %s is %s in total, but phase %s carries active power in the opposite direction "
                    "(unbalanced feeder)." % (n, WORD[r["sign"]], " and ".join(odd)))

    heading("LOAD FLOW COMPARISON")
    rows = []
    for n in DEV:
        a, b = lf[0]["dev"][n], lf[1]["dev"][n]
        rows.append([n, signed(max(a["I"]), a["sign"]), signed(max(b["I"]), b["sign"]),
                     "%+.1f" % (max(b["I"]) - max(a["I"])), WORD[a["sign"]], WORD[b["sign"]]])
    table(["Device", "Without DG (A)", "With DG (A)", "Change in magnitude (A)", "Direction without DG", "Direction with DG"],
          rows, "LoadFlow_comparison.csv")
    r2a, r2b = lf[0]["dev"]["R2"], lf[1]["dev"]["R2"]
    if r2a["sign"] != r2b["sign"]:
        say("The DG reverses the load current through R2: %.0f kW forward without DG, %.0f kW towards 632 with DG." % (
            r2a["P"], -r2b["P"]))
    check(all(lf[0]["dev"][n]["sign"] > 0 for n in DEV), "load flow without DG: R1 and R2 both forward")
    r1b = lf[1]["dev"]["R1"]
    odd = [p for p, s_ in zip("ABC", r1b["sign_ph"]) if s_ < 0]
    check(r1b["sign"] > 0, "load flow with DG: R1 forward in total (%.0f kW from the grid)%s" % (
        r1b["P"], "; phase %s exports towards the grid" % " and ".join(odd) if odd else ""))

    # ---- voltages -----------------------------------------------------------------------------
    for dg, step in ((0, 3), (1, 4)):
        heading("%d. BUS VOLTAGE %s  (phase-to-ground)" % (step, "WITHOUT DG" if dg == 0 else "WITH DG"))
        rows = [[b, p, "%.4f" % v[0], "%.4f" % v[1], "%.2f" % v[2]] for b in BUSES for p, v in lf[dg]["bus"][b].items()]
        table(["Bus", "Phase", "Voltage (kV)", "Voltage (pu)", "Angle (deg)"], rows,
              "%d_BusVoltage_DG_%s.csv" % (step, "in" if dg else "out"))
    heading("VOLTAGE COMPARISON")
    rows = []
    for b in BUSES:
        for p, a in lf[0]["bus"][b].items():
            c = lf[1]["bus"][b].get(p)
            rows.append([b, p, "%.4f" % a[0], "%.4f" % c[0], "%+.4f" % (c[0] - a[0]), "%.4f" % a[1], "%.4f" % c[1]])
    table(["Bus", "Phase", "V without DG (kV)", "V with DG (kV)", "dV (kV)", "V without DG (pu)", "V with DG (pu)"],
          rows, "BusVoltage_comparison.csv")
    say("Bus DG is the 0.69 kV generator terminal, 634 the 0.48 kV side of XFM-1; all other buses are 4.16 kV. "
        "Without DG the generator terminal is energised through its transformer, at no load.")

    # ---- phases ---------------------------------------------------------------------------------
    heading("PHASES PRESENT AT EACH BUS (from the model's load flow) AND FAULT TYPES THAT DO NOT EXIST THERE")
    table(["Bus", "Phases present", "Fault types not applicable"],
          [[n, present[n], ", ".join(missing.get(n, [])) or "-"] for n in NODE_ORDER])

    # ---- short circuits -------------------------------------------------------------------------
    head = ["Faulted bus", "Fault type", "Phases", "Zf (ohm)", "Fault current (A)", "R1 current (A)", "R1 sign",
            "R1 direction", "R2 current (A)", "R2 sign", "R2 direction"]
    mx, mn = {}, {}
    for dg, step, case in ((0, 5, "CASE A - DG DISCONNECTED"), (1, 6, "CASE B - DG CONNECTED")):
        tag = "in" if dg else "out"
        heading("%d. SHORT CIRCUIT %s  (%s) - every fault, current through R1 and R2" % (
            step, "WITHOUT DG" if dg == 0 else "WITH DG", case))
        table(head, fault_rows(sc[dg]), "%d_ShortCircuit_DG_%s.csv" % (step, tag))
        say("Currents are the largest phase value. 'no current' = below 1 A (no source behind the recloser for this fault).")

        say("")
        say("If,max at each fault location, %s (bolted, largest of the applicable fault types):" % ("with DG" if dg else "without DG"))
        rows = []
        for n in NODE_ORDER:
            r = mx.setdefault(dg, {}).setdefault(n, ifmax(sc[dg], n))
            d1, d2 = r["dev"]["R1"], r["dev"]["R2"]
            note = "" if "LLL" not in missing.get(n, []) else \
                "3-phase fault not applicable at this location; maximum fault current is obtained from %s fault." % r["type"]
            if not note and r["type"] != "LLL":
                note = "3-phase fault exists here but the %s fault gives the larger phase current." % r["type"]
            rows.append([n, f1(max(r["ifault"])), r["type"], r["phases"], signed(d1["mag"], d1["sign"]),
                         signed(d2["mag"], d2["sign"]), note])
        table(["Bus", "If,max (A)", "Fault type", "Faulted phases", "R1 (A)", "R2 (A)", "Comment"], rows,
              "Ifmax_DG_%s.csv" % tag)

        say("")
        say("If,min of each protection section, %s (LG through %g ohm at the farthest node):" % (
            "with DG" if dg else "without DG", RF_MIN))
        mn[dg] = ifmin_rows(sc[dg])
        table(["Protection section", "Farthest node", "Line length to it", "Fault type", "Faulted phase", "Zf (ohm)",
               "Fault current (A)", "If,min through the section (A)", "Lowest LG-3-ohm current in the section"],
              [[m["section"], m["far"], "%.0f" % m["dist"], "LG", m["phase"], "%g" % RF_MIN, f1(m["ifault"]), f1(m["isec"]),
                "%.1f A (fault at %s, phase %s)" % (m["low"], m["low_node"], m["low_phase"])] for m in mn[dg]],
              "Ifmin_DG_%s.csv" % tag)
        say("Line lengths are in the model's length unit (feet). At a node with more than one phase the phase with "
            "the smaller section current is given. A 3-ohm fault draws about as much as the feeder load, so the "
            "current through a section (complete method) contains the load current as well as the fault current.")

    # ---- comparison ----------------------------------------------------------------------------
    heading("DG OFF VS DG ON - FAULT CURRENT (If,max fault of each bus)")
    rows = []
    for n in NODE_ORDER:
        a, b = mx[0][n], mx[1][n]
        rows.append([n, a["type"] + (" " + a["phases"]), f1(max(a["ifault"])),
                     b["type"] + (" " + b["phases"]), f1(max(b["ifault"])),
                     signed(a["dev"]["R1"]["mag"], a["dev"]["R1"]["sign"]), signed(b["dev"]["R1"]["mag"], b["dev"]["R1"]["sign"]),
                     signed(a["dev"]["R2"]["mag"], a["dev"]["R2"]["sign"]), signed(b["dev"]["R2"]["mag"], b["dev"]["R2"]["sign"])])
    table(["Bus", "Fault without DG", "If,max without DG (A)", "Fault with DG", "If,max with DG (A)", "R1 without DG (A)",
           "R1 with DG (A)", "R2 without DG (A)", "R2 with DG (A)"], rows, "Comparison_fault_current.csv")
    heading("DG OFF VS DG ON - If,min")
    table(["Protection section", "Farthest node", "Fault", "Zf (ohm)", "If,min without DG (A)", "If,min with DG (A)"],
          [[a["section"], a["far"], "LG " + a["phase"], "%g" % RF_MIN, f1(a["isec"]), f1(b["isec"])]
           for a, b in zip(mn[0], mn[1])], "Comparison_Ifmin.csv")

    # ---- validation ----------------------------------------------------------------------------
    bolted = {dg: [r for r in sc[dg] if r["rf"] == 0.0] for dg in (0, 1)}
    up = [r for r in bolted[1] if r["node"] in UPSTREAM_OF_R2]
    dn = [r for r in bolted[1] if r["node"] in DOWNSTREAM_OF_R2]
    bad = [r for r in up if r["dev"]["R2"]["sign"] != -1]
    check(not bad, "with DG, R2 is reverse for all %d bolted faults upstream of R2 (%s)%s" % (
        len(up), ", ".join(UPSTREAM_OF_R2), "" if not bad else " - EXCEPT " + ", ".join(
            "%s %s %s (%s)" % (r["node"], r["type"], r["phases"], WORD[r["dev"]["R2"]["sign"]]) for r in bad)))
    bad = [r for r in dn if r["dev"]["R2"]["sign"] != 1]
    check(not bad, "with DG, R2 is forward for all %d bolted faults downstream of R2 (%s)%s" % (
        len(dn), ", ".join(DOWNSTREAM_OF_R2), "" if not bad else " - EXCEPT " + ", ".join(
            "%s %s %s" % (r["node"], r["type"], r["phases"]) for r in bad)))
    for dg in (0, 1):
        bad = [r for r in sc[dg] if r["dev"]["R1"]["sign"] != 1]
        check(not bad, "%s DG, R1 is forward for all %d faults%s" % ("with" if dg else "without", len(sc[dg]),
              "" if not bad else " - EXCEPT " + ", ".join("%s %s %s" % (r["node"], r["type"], r["phases"]) for r in bad)))
    bad = [r for r in bolted[0] if r["node"] in DOWNSTREAM_OF_R2 and r["dev"]["R2"]["sign"] != 1]
    check(not bad, "without DG, R2 is forward for all bolted faults downstream of R2")
    worst = max((r for r in bolted[0] if r["node"] in UPSTREAM_OF_R2), key=lambda r: r["dev"]["R2"]["mag"])
    check(worst["dev"]["R2"]["mag"] < 1.25 * max(lf[0]["dev"]["R2"]["I"]),
          "without DG, R2 carries only load-level current for faults upstream of it (largest value %.0f A at %s %s, "
          "towards the loads behind it; load current %.0f A)" % (worst["dev"]["R2"]["mag"], worst["node"], worst["type"],
                                                                 max(lf[0]["dev"]["R2"]["I"])))
    key = lambda r: (r["node"], r["type"], r["phases"], r["rf"])
    off = {key(r): r for r in sc[0]}
    same = set(off) == set(key(r) for r in sc[1])
    check(same, "the same %d faults (location, type, phases, Zf) were calculated without and with DG" % len(sc[0]))
    lower = [r for r in bolted[1] if key(r) in off and max(r["ifault"]) < 0.999 * max(off[key(r)]["ifault"])]
    check(not lower, "the DG raises (never lowers) the bolted fault current at every bus%s" % (
        "" if not lower else " - EXCEPT " + ", ".join("%s %s %s" % (r["node"], r["type"], r["phases"]) for r in lower)))
    dev = max(abs(r["dev"]["R1"]["mag"] - r["dev"]["R2"]["mag"]) / max(r["ifault"])
              for r in bolted[0] if r["node"] in DOWNSTREAM_OF_R2)
    check(dev < 0.15, "without DG, R1 and R2 carry the same fault current for faults downstream of R2 "
                      "(largest difference %.1f %% of the fault current: load between them)" % (100 * dev))
    check(all(max(mx[dg][n]["ifault"]) >= max(r["ifault"]) for dg in (0, 1) for n in NODE_ORDER
              for r in bolted[dg] if r["node"] == n), "If,max is the largest bolted fault current of the applicable types at every bus")
    check(all(m["isec"] < max(mx[dg][m["far"]]["ifault"]) for dg in (0, 1) for m in mn[dg]),
          "If,min (LG, %g ohm, farthest node) is below If,max in every section" % RF_MIN)
    # If,min rule: the paper's (farthest node) is kept for the comparison with its Table II.  Where
    # another node gives a lower current, that lower value is listed beside it and is the one used for
    # the sensitivity check below (step 5 of the paper's method: pickup below the minimum fault current).
    off_far = [m for dg in (0, 1) for m in mn[dg] if m["low"] < 0.98 * m["isec"]]
    check(True, "If,min rule: farthest node for Table II; the lowest LG-%g-ohm current of each section is "
                "listed beside it%s" % (RF_MIN, "" if not off_far else " - it is lower than the farthest-node value in: " +
                "; ".join(sorted({"%s (farthest %s, lowest at %s)" % (m["section"], m["far"], m["low_node"]) for m in off_far}))))
    for dg in (0, 1):
        for name, sec in (("R1", "RG60-632"), ("R2", "632-671")):
            m = [x for x in mn[dg] if x["section"] == sec][0]
            ip = OLF * max(lf[0]["dev"][name]["I"])
            check(ip < m["low"], "sensitivity %s DG: %s pickup by eq. (3), %.2f x %.1f A = %.1f A, against the lowest "
                  "LG-%g-ohm current through it, %.1f A (fault at %s, phase %s)%s" % (
                      "with" if dg else "without", name, OLF, max(lf[0]["dev"][name]["I"]), ip, RF_MIN,
                      m["low"], m["low_node"], m["low_phase"],
                      "" if ip < m["low"] else " - BELOW THE PICKUP: the DG supplies part of the fault and of the load, so "
                      "this recloser does not see high-resistance faults at the far end"))
    check(bool(missing), "phase-limited buses handled: %s" % "; ".join(
        "%s (%s) no %s" % (n, present[n], "/".join(missing[n])) for n in NODE_ORDER if n in missing))

    sym.SetAttribute("outserv", dg_state)
    ldf.Execute()
    clean_variation()
    check(protection_snapshot() == before, "relay pickups, time dials, curves and fuse types are unchanged by this study")

    heading("VALIDATION BEFORE RELAY COORDINATION")
    for status, text in checks:
        say("  [%-5s] %s" % (status, text))
    n_bad = sum(s != "PASS" for s, _ in checks)
    say("")
    say("%d of %d checks passed.%s" % (len(checks) - n_bad, len(checks),
        " The database is complete; relay pickup, fast/delayed operation, TDS, TCC and CTI can follow." if not n_bad else
        " Items marked CHECK must be looked at before relay coordination."))
    say("Files: " + OUT)
    with open(os.path.join(OUT, "Database_Report.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(REPORT) + "\n")


if __name__ == "__main__":
    main()
