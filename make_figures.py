"""
Table IV and Figs. 7-9, 11-17 of Yousaf et al. (2022) for the IEEE 13-node model.

Reads Fault_Study.csv (fault currents from PowerFactory, Fault_Study.py) and computes
operating times with the model's curves:
  R1        GE IAC extremely inverse, Ip 720 A, TDS 0.5 / 10
  R2 fw     GE IAC extremely inverse, Ip 600 A, TDS 0.8 / 4.0 (conventional recloser)
  R2 rv     reverse setting of the dual-setting recloser (DSDR): Ip = 1.25 x reverse load
            current with the DG (eq. 12); TDS chosen as in step 8 of the method so the fast
            curve is below and the delayed curve above every primary fuse for faults
            upstream of R2 (margin MARGIN)
  fuses     eq. (6): MMT = 10^b_i * I^-1.8 (Table III b_i), TCT at K_TCT x the current

Coordination (Figs. 14, 17) is "held" when every recloser feeding the fault trips fast
before the primary fuse melts and the fuse clears before the recloser's delayed trip.
Upstream of R2 both R1 and R2 feed the fault (R2 from the DG, reverse); downstream only R2.

Run with Python 3 (matplotlib). Output: Result/Figures/*.png, Result/Table_IV_model.csv,
Table_IV_comparison.csv.
"""

import csv
import os
from collections import defaultdict
from math import log10

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

DIR = os.path.dirname(os.path.abspath(__file__))
RES_DIR = os.path.join(DIR, "Result")
FIG_DIR = os.path.join(RES_DIR, "Figures")

IAC_EI = (0.0040, 0.6379, 0.6200, 1.7872, 0.2461)
OLF = 1.25
A_FUSE = -1.8
K_TCT = 1.21            # clearing / melting current ratio (template fuse, Add_Fuses.py)
MARGIN = 0.8            # DSDR reverse: fast <= 0.8 x MMT, delayed >= TCT / 0.8
B = {"F632": 6.38, "F633": 6.83, "F634": 8.32, "F645": 6.65, "F646": 6.67, "F-DL": 6.54,
     "F671": 6.08, "F671-1": 5.85, "F692": 6.13, "F692-R": 6.14, "F675": 6.19,
     "F671-2": 5.87, "F684": 6.15, "F611": 6.19, "F652": 6.17}

R1_NODES = ["632", "633", "634", "645", "646", "nDL"]          # upstream of R2
R2_NODES = ["671", "680", "692", "675", "684", "611", "652"]
NODE_LABEL = {"nDL": "DL"}
# fuses in the faulted path, upstream first (Fig. 6 placement, Add_Fuses.py)
PATH = {"632": [], "633": ["F633"], "634": ["F633", "F634"], "645": ["F632"],
        "646": ["F632", "F646"], "nDL": ["F-DL"], "671": [], "680": ["F671"],
        "692": ["F671-1"], "675": ["F671-1", "F692-R"], "684": ["F671-2"],
        "611": ["F671-2", "F684"], "652": ["F671-2", "F652"]}
FAULTS = ["LG", "LL", "LLG", "LLL"]

# Paper, Table IV: node -> R1 fast, R1 delayed, R2 fast, R2 delayed, fuse MMT
PAPER_T4 = {"632": (0.070, 1.398, 0.045, 0.514, None), "633": (0.094, 1.880, 0.052, 0.706, 0.163),
            "645": (0.105, 2.095, 0.087, 1.659, 0.276), "646": (0.128, 2.555, 0.103, 2.046, 0.181),
            "nDL": (0.087, 1.733, 0.076, 1.402, 0.248), "671": (0.105, 2.091, 0.068, 1.113, None),
            "692": (0.115, 2.307, 0.072, 1.258, 0.175), "675": (0.121, 2.414, 0.074, 1.332, 0.185),
            "684": (0.125, 2.507, 0.075, 1.394, 0.205), "680": (0.137, 2.747, 0.079, 1.555, None),
            "611": (0.326, 6.523, 0.146, 4.385, 0.417), "652": (0.676, 13.525, 0.143, 9.370, 0.233)}
# Paper, Figs. 14 and 17 (row = fault type, column = node; 1 held, 0 lost, None N/A)
PAPER_NODES = ["632", "633", "634", "645", "646", "671", "692", "675", "680", "684", "652",
               "611", "nDL"]
# read from the paper's figures; columns in PAPER_NODES order, "+" held, "x" lost, "-" N/A
PAPER_GRID = {
    "Fig14": {"LG": "++-x+++++++++", "LL": "++-xx+++++--+",
              "LLG": "+x-xx++x++--+", "LLL": "+x---++x+---+"},
    "Fig17": {"LG": "++-++++++++++", "LL": "++-+++++++--+",
              "LLG": "++-+++++++--+", "LLL": "++---++++---+"},
}
NOT_COORDINATED = {"634"}   # LV-side fuse: not coordinated with the reclosers (paper, Sec. IV)

# colours: reference palette, light mode
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"          # blue, orange, aqua
GOOD, CRIT = "#0ca30c", "#d03b3b"


# ---- curves --------------------------------------------------------------------------------
def iac(m):
    a, b, c, d, e = IAC_EI
    x = m - c
    return a + b / x + d / x ** 2 + e / x ** 3 if m > 1.0 else float("inf")


class Recloser:
    def __init__(self, name, ip, tds_f, tds_d):
        self.name, self.ip, self.tds_f, self.tds_d = name, ip, tds_f, tds_d

    def fast(self, i):
        return self.tds_f * iac(i / self.ip)

    def delayed(self, i):
        return self.tds_d * iac(i / self.ip)


def mmt(f, i):
    return 10.0 ** B[f] * i ** A_FUSE if i > 0 else float("inf")


def tct(f, i):
    return mmt(f, i / K_TCT)


# ---- data ---------------------------------------------------------------------------------
def load():
    data = defaultdict(dict)       # (study, case/location, fault, DG, pct) -> {device: A}
    lf = {}
    with open(os.path.join(RES_DIR, "Fault_Study.csv")) as fh:
        for r in csv.DictReader(fh):
            i = float(r["I_A"]) if r["I_A"] else None
            if r["study"] == "loadflow":
                # Fault_Study.py (first version) scaled load-flow amps by 1000
                lf[(r["device"], int(r["DG"]))] = i / 1000.0 if i and i > 5e3 else i
                continue
            key = (r["study"], r["case"] or r["location"], r["fault"], int(r["DG"]),
                   int(r["DG_pct"]))
            data[key][r["device"]] = i
    return data, lf


def fuse_current(res, fuse, node):
    """Current through a fuse. The distributed-load fuse is taken as carrying the whole
    fault current of a fault on its load drop (grid via R1 + DG via R2)."""
    if fuse == "F-DL":
        return (res.get("R1") or 0.0) + (res.get("R2") or 0.0)
    return res.get(fuse) or 0.0


def primary(node):
    return PATH[node][-1] if PATH[node] else None


# ---- DSDR reverse setting (step 8 of the method) ------------------------------------------
def design_r2_reverse(data, ip_rv):
    """TDS for R2 reverse: fast <= MARGIN x MMT and delayed >= TCT / MARGIN of the primary
    fuse for every fault upstream of R2 (DG in service)."""
    fmax, dmin = [], []
    for node in R1_NODES:
        f = primary(node)
        if f is None:
            continue
        for ft in FAULTS:
            res = data.get(("sweep", node, ft, 1, 100))
            if not res or res.get("R2") is None:
                continue
            k = iac(res["R2"] / ip_rv)
            if k == float("inf"):
                continue
            i_f = fuse_current(res, f, node)
            fmax.append(MARGIN * mmt(f, i_f) / k)
            dmin.append(tct(f, i_f) / MARGIN / k)
    return min(fmax), max(dmin)


# ---- coordination ---------------------------------------------------------------------------
def feeding_reclosers(node, res, r1, r2, dsdr):
    """(recloser, current) pairs that feed a fault at node."""
    if node in R1_NODES:
        return [(r1, res["R1"]), (dsdr if dsdr else r2, res["R2"])]
    return [(r2, res["R2"])]


def coordination(res, node, r1, r2, dsdr):
    """True held, False lost, None not applicable (no fuse / fault type absent)."""
    f = primary(node)
    if res is None or res.get("R1") is None or f is None or node in NOT_COORDINATED:
        return None
    i_f = fuse_current(res, f, node)
    t_melt, t_clear = mmt(f, i_f), tct(f, i_f)
    for rec, i in feeding_reclosers(node, res, r1, r2, dsdr):
        if i is None or i <= rec.ip:
            continue                               # does not pick up
        if not (rec.fast(i) < t_melt and t_clear < rec.delayed(i)):
            return False
    return True


# ---- plotting helpers ----------------------------------------------------------------------
def style(ax):
    ax.set_facecolor(SURFACE)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(100, 100000)
    ax.set_ylim(0.01, 1000)
    ax.grid(True, which="major", color=GRID, lw=0.8)
    ax.grid(True, which="minor", color=GRID, lw=0.4, alpha=0.6)
    for s in ax.spines.values():
        s.set_color(INK2)
        s.set_linewidth(0.8)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.set_xlabel("Current (A) at 4.16 kV", color=INK, fontsize=10)
    ax.set_ylabel("Time (s)", color=INK, fontsize=10)


def logspace(a, b, n=200):
    return [a * (b / a) ** (k / (n - 1.0)) for k in range(n)]


def draw_recloser(ax, rec, color, label):
    xs = logspace(rec.ip * 1.05, rec.ip * 20)
    ax.plot(xs, [rec.fast(x) for x in xs], color=color, lw=2, label=label + " fast")
    ax.plot(xs, [rec.delayed(x) for x in xs], color=color, lw=2, ls=(0, (5, 3)),
            label=label + " delayed")


def draw_fuse(ax, f, color):
    xs = logspace(100, 100000)
    lo = [mmt(f, x) for x in xs]
    hi = [tct(f, x) for x in xs]
    ax.fill_between(xs, lo, hi, color=color, alpha=0.22, lw=0)
    ax.plot(xs, lo, color=color, lw=1.5, label="%s (melt / clear)" % f)
    ax.plot(xs, hi, color=color, lw=1.5)


def mark(ax, i, t, color, text, dy=1.0):
    if not (0.01 < t < 1000):
        return
    ax.plot([i], [t], "o", ms=8, mfc=color, mec=SURFACE, mew=2, zorder=5)
    ax.annotate(text, (i, t), xytext=(8, 4 * dy), textcoords="offset points", fontsize=9,
                color=INK, zorder=6,
                bbox=dict(boxstyle="round,pad=0.2", fc=SURFACE, ec="none", alpha=0.9))


def tcc_figure(fname, title, subtitle, reclosers, fuses, paper_note):
    """reclosers: [(Recloser, current, colour, label)], fuses: [(fuse, current, colour)]."""
    fig, ax = plt.subplots(figsize=(7.2, 5.6), facecolor=SURFACE)
    style(ax)
    for rec, i, color, label in reclosers:
        draw_recloser(ax, rec, color, label)
    for f, i, color in fuses:
        draw_fuse(ax, f, color)
    for rec, i, color, label in reclosers:
        ax.axvline(i, color=color, lw=1, alpha=0.7)
        mark(ax, i, rec.fast(i), color, "%.3f s" % rec.fast(i), -2)
        mark(ax, i, rec.delayed(i), color, "%.3f s" % rec.delayed(i))
    for f, i, color in fuses:
        ax.axvline(i, color=color, lw=1, alpha=0.7)
        mark(ax, i, mmt(f, i), color, "%.3f s" % mmt(f, i))
    currents = ", ".join("%s %.0f A" % (lab, i) for _, i, _, lab in reclosers)
    currents += "".join(", %s %.0f A" % (f, i) for f, i, _ in fuses)
    fig.suptitle(title, x=0.08, ha="left", fontsize=12, color=INK, fontweight="bold")
    ax.set_title(subtitle + "\nFault current: " + currents, loc="left", fontsize=9,
                 color=INK2)
    leg = ax.legend(loc="upper right", fontsize=8, frameon=True, facecolor=SURFACE,
                    edgecolor=GRID)
    for t in leg.get_texts():
        t.set_color(INK)
    fig.text(0.08, 0.01, "Paper: " + paper_note, fontsize=8, color=INK2)
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    fig.savefig(os.path.join(FIG_DIR, fname), dpi=200, facecolor=SURFACE)
    plt.close(fig)


def grid_figure(fname, title, subtitle, status, paper=None):
    """Figs. 14/17: fault type x node, held / lost / not applicable."""
    fig, ax = plt.subplots(figsize=(9.5, 3.4), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    nodes = PAPER_NODES
    for c, node in enumerate(nodes):
        for r, ft in enumerate(FAULTS):
            s = status.get((node, ft))
            y = len(FAULTS) - 1 - r
            if s is None:
                ax.plot(c, y, marker="o", ms=20, mfc=SURFACE, mec=INK2, mew=1.2)
                ax.text(c, y, "–", ha="center", va="center", fontsize=12, color=INK2)
            else:
                col = GOOD if s else CRIT
                ax.plot(c, y, marker="o", ms=20, mfc=SURFACE, mec=col, mew=2)
                ax.text(c, y, "✓" if s else "✗", ha="center", va="center", fontsize=12,
                        color=col, fontweight="bold")
    ax.set_xticks(range(len(nodes)))
    ax.set_xticklabels([NODE_LABEL.get(n, n) for n in nodes], color=INK, fontsize=9)
    ax.set_yticks(range(len(FAULTS)))
    ax.set_yticklabels(list(reversed(FAULTS)), color=INK, fontsize=9)
    ax.set_xlim(-0.6, len(nodes) - 0.4)
    ax.set_ylim(-0.6, len(FAULTS) - 0.4)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    ax.set_xlabel("Faulted node", color=INK, fontsize=10)
    ax.set_ylabel("Fault type", color=INK, fontsize=10)
    held = sum(1 for v in status.values() if v)
    lost = sum(1 for v in status.values() if v is False)
    fig.suptitle(title, x=0.06, ha="left", fontsize=12, color=INK, fontweight="bold")
    ax.set_title("%s\n✓ held %d   ✗ lost %d   – not applicable (no fuse in the path or "
                 "fault type absent)" % (subtitle, held, lost), loc="left", fontsize=9,
                 color=INK2)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, fname), dpi=200, facecolor=SURFACE)
    plt.close(fig)


# ---- main ----------------------------------------------------------------------------------
def main():
    os.makedirs(FIG_DIR, exist_ok=True)
    data, lf = load()
    r1 = Recloser("R1", 720.0, 0.5, 10.0)
    r2 = Recloser("R2", 600.0, 0.8, 4.0)
    i_rv = lf.get(("R2", 1))
    ip_rv = OLF * i_rv
    tf, td = design_r2_reverse(data, ip_rv)
    dsdr = Recloser("R2 rv", ip_rv, round(tf, 3), round(td, 3))
    print("Load flow with DG: R2 reverse current %.1f A -> Ip,rv = %.1f A" % (i_rv, ip_rv))
    print("DSDR reverse TDS: fast %.3f, delayed %.3f (IAC EI)" % (dsdr.tds_f, dsdr.tds_d))

    def case(name):
        return data[("case", name, next(k[2] for k in data if k[0] == "case" and k[1] == name),
                     1, 100)]

    # ---- Table IV -------------------------------------------------------------------------
    rows = []
    for node in PAPER_T4:
        best = None
        for ft in reversed(FAULTS):                 # largest fault type that exists
            res = data.get(("sweep", node, ft, 1, 100))
            if res and res.get("R1") is not None:
                best = (ft, res)
                break
        ft, res = best
        r2use = dsdr if node in R1_NODES else r2
        f = primary(node)
        fm = mmt(f, fuse_current(res, f, node)) if f else None
        rows.append((NODE_LABEL.get(node, node), ft, res["R1"], r1.fast(res["R1"]),
                     r1.delayed(res["R1"]), res["R2"], r2use.fast(res["R2"]),
                     r2use.delayed(res["R2"]), f, fm) + PAPER_T4[node])
    with open(os.path.join(RES_DIR, "Table_IV_model.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Node", "Fault", "I_R1 (A)", "R1 fast (s)", "R1 delayed (s)", "I_R2 (A)",
                    "R2 fast (s)", "R2 delayed (s)", "Primary fuse", "Fuse MMT (s)",
                    "Paper R1 fast", "Paper R1 delayed", "Paper R2 fast", "Paper R2 delayed",
                    "Paper fuse MMT"])
        for r in rows:
            w.writerow([r[0], r[1], "%.0f" % r[2], "%.3f" % r[3], "%.3f" % r[4], "%.0f" % r[5],
                        "%.3f" % r[6] if r[6] < 1e3 else "no trip",
                        "%.3f" % r[7] if r[7] < 1e3 else "no trip",
                        r[8] or "---", "%.3f" % r[9] if r[9] else "---"] +
                       ["---" if v is None else "%.3f" % v for v in r[10:]])
    print("\nTABLE IV (model, DG in service, bolted fault of the largest type at the node)")
    print("%-4s %-4s | %6s %7s | %6s %7s | %-7s %6s || paper %6s %7s %6s %7s %6s" % (
        "Node", "flt", "R1 F", "R1 D", "R2 F", "R2 D", "fuse", "MMT", "R1 F", "R1 D", "R2 F",
        "R2 D", "MMT"))
    for r in rows:
        f2 = lambda v: "%6.3f" % v if v is not None and v < 1e3 else "   ---"  # noqa: E731
        print("%-4s %-4s | %s %s | %s %s | %-7s %s || paper %s %s %s %s %s" % (
            r[0], r[1], f2(r[3]), f2(r[4]).rjust(7), f2(r[6]), f2(r[7]).rjust(7), r[8] or "---",
            f2(r[9]), f2(r[10]), f2(r[11]).rjust(7), f2(r[12]), f2(r[13]).rjust(7), f2(r[14])))

    # ---- TCC figures ------------------------------------------------------------------------
    c = case("Fig8")
    tcc_figure("Fig08_SLG_611.png", "Fig. 8 (model): SLG fault at node 611",
               "R2 (conventional) with the series fuses F671-2 and F684; DG in service",
               [(r2, c["R2"], C1, "R2")], [(f, c[f], col) for f, col in
                                            (("F684", C2), ("F671-2", C3))],
               "R2 fast 0.207 s, F684 0.476 s, F671-2 1.456 s, R2 delayed 2.472 s at 1976 A")
    c = case("Fig9")
    tcc_figure("Fig09_LLG_692-675.png", "Fig. 9 (model): LLG fault at mid 692–675, Rf 1 Ω",
               "R2 (conventional) with the series fuses F671-1 and F692-R; DG in service",
               [(r2, c["R2"], C1, "R2")], [(f, c[f], col) for f, col in
                                            (("F692-R", C2), ("F671-1", C3))],
               "R2 fast 0.141 s, fuses 0.217 s / 0.546 s, R2 delayed 1.483 s")
    c = case("Fig11")
    tcc_figure("Fig11_LL_646.png", "Fig. 11 (model): LL fault at node 646, Rf 1 Ω",
               "R1 with the series fuses F632 and F646; DG in service",
               [(r1, c["R1"], C1, "R1")], [(f, c[f], col) for f, col in
                                            (("F646", C2), ("F632", C3))],
               "R1 fast 0.134 s, F646 0.202 s, F632 1.096 s, R1 delayed 2.690 s at 3492 A")
    c = case("Fig12")
    tcc_figure("Fig12_LL_645_conventional_R2.png",
               "Fig. 12 (model): LL fault at node 645, Rf 1.5 Ω",
               "Conventional R2 (forward settings) sees only the DG contribution, in reverse",
               [(r2, c["R2"], C1, "R2")], [(f, c[f], col) for f, col in
                                            (("F646", C2), ("F632", C3))],
               "R2 fast 0.419 s, R2 delayed 16.683 s, F632 25.440 s")
    c = case("Fig13")
    tcc_figure("Fig13_3ph_632-633.png",
               "Fig. 13 (model): 3-phase fault at 10 % of line 632–633",
               "Conventional R2 (reverse DG current) and F633 (grid + DG current)",
               [(r2, c["R2"], C1, "R2")], [("F633", c["F633"], C2)],
               "R2 fast 0.079 s and delayed 1.556 s at 3361 A, F633 0.022 s at 8517 A")
    c = case("Fig15-16")
    tcc_figure("Fig15_LL_646_DSDR_R2.png",
               "Fig. 15 (model): solid LL fault at node 646, R2 as DSDR",
               "R2 reverse settings (Ip %.0f A, TDS %.2f / %.2f) with F646 and F632" % (
                   dsdr.ip, dsdr.tds_f, dsdr.tds_d),
               [(dsdr, c["R2"], C1, "R2 rev")], [(f, c[f], col) for f, col in
                                                 (("F646", C2), ("F632", C3))],
               "R2rv fast 0.103 s, delayed 2.046 s at 1542 A; F646 0.181 s, F632 0.411 s")
    tcc_figure("Fig16_LL_646_R1.png", "Fig. 16 (model): solid LL fault at node 646",
               "R1 with the series fuses F646 and F632; DG in service",
               [(r1, c["R1"], C1, "R1")], [(f, c[f], col) for f, col in
                                            (("F646", C2), ("F632", C3))],
               "R1 fast 0.128 s, F646 0.181 s, F632 0.411 s, R1 delayed 2.555 s at 3606 A")

    # ---- Figs. 14 and 17 --------------------------------------------------------------------
    comparison = []
    for fname, title, sub, use_dsdr in (
            ("Fig14_coordination_conventional.png",
             "Fig. 14 (model): recloser–fuse coordination without the DSDR",
             "Conventional R2 (one setting for both directions); DG in service", False),
            ("Fig17_coordination_DSDR.png",
             "Fig. 17 (model): recloser–fuse coordination with the DSDR",
             "R2 with separate reverse settings (Ip %.0f A, TDS %.2f / %.2f)" % (
                 dsdr.ip, dsdr.tds_f, dsdr.tds_d), True)):
        st = {(n, ft): coordination(data.get(("sweep", n, ft, 1, 100)), n, r1, r2,
                                    dsdr if use_dsdr else None)
              for n in PAPER_NODES for ft in FAULTS}
        grid_figure(fname, title, sub, st)
        paper = PAPER_GRID["Fig17" if use_dsdr else "Fig14"]
        same, diffs = 0, []
        for n_i, n in enumerate(PAPER_NODES):
            for ft in FAULTS:
                pv = {"+": True, "x": False, "-": None}[paper[ft][n_i]]
                if pv is None or st[(n, ft)] is None:
                    continue
                if pv == st[(n, ft)]:
                    same += 1
                else:
                    diffs.append("%s %s (paper %s, model %s)" % (
                        NODE_LABEL.get(n, n), ft, "held" if pv else "lost",
                        "held" if st[(n, ft)] else "lost"))
        comparison.append((title.split(":")[0], same, diffs))
        print("\n%s" % title)
        for ft in FAULTS:
            print("  %-4s %s" % (ft, " ".join(
                {None: "  -", True: "  +", False: "  x"}[st[(n, ft)]] for n in PAPER_NODES)))
        print("       " + " ".join("%3s" % NODE_LABEL.get(n, n)[-3:] for n in PAPER_NODES))

    print("\nFigs. 14/17 against the paper (cells applicable in both):")
    for title, same, diffs in comparison:
        print("  %s: %d agree, %d differ" % (title, same, len(diffs)))
        for d in diffs:
            print("      " + d)

    # ---- series fuses, eq. (8): MMT(upstream) > 1.33 TCT(downstream) ------------------------
    print("\nSeries fuses, eq. (8), bolted fault below the downstream fuse, DG in service:")
    for node in R1_NODES + R2_NODES:
        if len(PATH[node]) < 2 or node in NOT_COORDINATED:
            continue
        up, down = PATH[node][-2], PATH[node][-1]
        for ft in reversed(FAULTS):
            res = data.get(("sweep", node, ft, 1, 100))
            if res and res.get(down):
                t_up, t_dn = mmt(up, res[up]), tct(down, res[down])
                print("  fault %-4s %-4s %-6s MMT %.3f s vs %-6s TCT %.3f s -> %s" % (
                    node, ft, up, t_up, down, t_dn,
                    "OK" if t_up > 1.33 * t_dn else "VIOLATED (upstream fuse melts first)"))
                break

    # ---- Fig. 7 -----------------------------------------------------------------------------
    levels = sorted({k[4] for k in data if k[0] == "dg"})
    series = {}
    for node, fuse, rec_name in (("633", "F633", "R1"), ("671", "F671", "R2")):
        cti = []
        for p in levels:
            res = data[("dg", node, "LLL", int(p > 0), p)]
            rec = r1 if rec_name == "R1" else r2
            # a fault just below F671 carries grid (via R2) + DG (via 671-692) current
            i_f = res["F633"] if fuse == "F633" else res["R2"] + (res.get("F671-1") or 0)
            cti.append(mmt(fuse, i_f) - rec.fast(res[rec_name]))
        series[node] = [100.0 * (v - cti[0]) / cti[0] for v in cti]
        print("\nFig. 7 %s: CTI %s s" % (node, ", ".join("%.3f" % v for v in cti)))
    fig, ax = plt.subplots(figsize=(7.2, 4.4), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    ax.axhline(0, color=INK2, lw=0.8)
    for (node, vals), col, lab in zip(series.items(), (C1, C2),
                                      ("Node 633 (internal, R1–F633)",
                                       "Node 671 (external, R2–F671)")):
        ax.plot(levels, vals, color=col, lw=2, marker="o", ms=8, mec=SURFACE, mew=2,
                label=lab)
        ax.annotate("%+.0f %%" % vals[-1], (levels[-1], vals[-1]), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=9, color=INK)
    ax.set_xticks(levels)
    ax.set_xticklabels(["%d %%" % p for p in levels], color=INK2, fontsize=9)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(True, axis="y", color=GRID, lw=0.8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(INK2)
    ax.set_xlabel("DG penetration (% of 4.05 MVA)", color=INK, fontsize=10)
    ax.set_ylabel("Change in CTI (%)", color=INK, fontsize=10)
    fig.suptitle("Fig. 7 (model): change in recloser–fuse CTI with DG penetration",
                 x=0.08, ha="left", fontsize=12, color=INK, fontweight="bold")
    ax.set_title("CTI = fuse melting time − recloser fast time, bolted 3-phase fault; "
                 "relative to no DG", loc="left", fontsize=9, color=INK2)
    ax.legend(fontsize=8, frameon=False, labelcolor=INK)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "Fig07_CTI_vs_DG.png"), dpi=200, facecolor=SURFACE)
    plt.close(fig)
    print("\nFigures saved in", FIG_DIR)


main()
