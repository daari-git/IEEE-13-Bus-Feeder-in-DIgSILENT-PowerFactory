"""
CTI against DG penetration: conventional scheme (../Penetration_Study) against the DSDR scheme (this folder).

Both studies use the same seven DG levels and the same two faults:
  633  three-phase fault at 633 (upstream of R2): fuse F633 against R1, R2 carries the DG share in reverse
  671  line-to-line fault at 684 (lateral from 671): fuse F671-2 against R2 forward
Two quantities per case:
  CTI            = t_MMT(fuse) - t_fast(recloser of the pair: R1 at 633, R2 at 671)      (as in Fig. 7)
  margin (last)  = t_MMT(fuse) - the LAST fast trip of the reclosers that feed the fault through the fuse
                   633: later of R1 fast and R2 fast (conventional: R2's forward unit, non-directional;
                        DSDR: R2's reverse group); a recloser that does not pick up is left out
                   671: R2 forward fast
  ring %         = 100 x CTI / sum of |CTI| over the seven levels (each ring = 100 %)

Writes results/CTI_conventional_vs_DSDR.csv, results/Fig07_DSDR_ring.png, results/CTI_conventional_vs_DSDR.png,
results/Summary.md.
"""

import csv
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
CONV = {int(k): v for k, v in json.load(open(os.path.join(os.path.dirname(HERE), "Penetration_Study", "results",
                                                         "penetration_results.json"))).items()}
DSDR = {int(k): v for k, v in json.load(open(os.path.join(RES, "penetration_results.json"))).items()}
P = sorted(DSDR)
KEY = {"633": "633 LLL", "671": "671 LL"}
INF = float("inf")
BLUE, ORANGE, INK2, GRID, RED = "#2a78d6", "#eb6834", "#55534e", "#d9d8d4", "#d03b3b"


def f(D, p, n):
    return D[p]["faults"][KEY[n]]


def last_conv(p, n):
    """conventional scheme: last fast trip of the reclosers feeding the fault through the fuse"""
    x = f(CONV, p, n)
    ts = [x["t_R1_fast"], x["t_R2_fast"]] if n == "633" else [x["t_R2_fast"]]
    ts = [t for t in ts if t < 1e6]
    return max(ts) if ts else INF


def ring(vals):
    tot = sum(abs(v) for v in vals)
    return [100.0 * v / tot for v in vals]


cti = {(s, n): [f(D, p, n)["CTI_s"] for p in P] for s, D in (("conv", CONV), ("dsdr", DSDR)) for n in KEY}
marg = {("conv", n): [f(CONV, p, n)["t_fuse_MMT"] - last_conv(p, n) for p in P] for n in KEY}
marg.update({("dsdr", n): [f(DSDR, p, n)["margin_last_s"] for p in P] for n in KEY})
rings = {k: ring(v) for k, v in cti.items()}

with open(os.path.join(RES, "CTI_conventional_vs_DSDR.csv"), "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["DG penetration %",
                "633 fuse (conv / DSDR)", "633 I fuse (A) conv", "633 I fuse (A) DSDR", "633 t_MMT conv (s)", "633 t_MMT DSDR (s)",
                "633 R1 fast (s)", "633 R2 fast conv (s)", "633 R2 reverse fast DSDR (s)",
                "633 CTI vs R1 conv (ms)", "633 CTI vs R1 DSDR (ms)", "633 margin to last fast trip conv (ms)",
                "633 margin to last fast trip DSDR (ms)",
                "671 CTI vs R2 conv (ms)", "671 CTI vs R2 DSDR (ms)", "633 ring % conv", "633 ring % DSDR",
                "671 ring % conv", "671 ring % DSDR"])
    for k, p in enumerate(P):
        a, b = f(CONV, p, "633"), f(DSDR, p, "633")
        ms = lambda v: "%+.0f" % (1000 * v) if abs(v) < 1e6 else "n/a"
        w.writerow([p, "250E / 400E", a["I_fuse"], b["I_fuse"], "%.3f" % a["t_fuse_MMT"], "%.3f" % b["t_fuse_MMT"],
                    "%.3f" % b["t_R1_fast"], "%.3f" % a["t_R2_fast"] if a["t_R2_fast"] < 1e6 else "no trip",
                    "%.3f" % b["t_R2rev_fast"] if b["t_R2rev_fast"] < 1e6 else "no trip",
                    ms(cti[("conv", "633")][k]), ms(cti[("dsdr", "633")][k]), ms(marg[("conv", "633")][k]),
                    ms(marg[("dsdr", "633")][k]), ms(cti[("conv", "671")][k]), ms(cti[("dsdr", "671")][k]),
                    "%+.1f" % rings[("conv", "633")][k], "%+.1f" % rings[("dsdr", "633")][k],
                    "%+.1f" % rings[("conv", "671")][k], "%+.1f" % rings[("dsdr", "671")][k]])

# ---- the two doughnuts side by side -----------------------------------------------------------
cols = ["#0070c0", "#bfbfbf", "#ffd500", "#ffa600", "#4472c4", "#c00000", "#ff3b30"]
fig, axes = plt.subplots(1, 2, figsize=(11.2, 5.4))
for ax, s, title in ((axes[0], "conv", "Without DSDR (conventional)"), (axes[1], "dsdr", "With DSDR (revised fuses)")):
    for n, radius in (("671", 1.0), ("633", 0.76)):
        vals = rings[(s, n)]
        sizes = [max(abs(v), 0.5) for v in vals]
        ax.pie(sizes, radius=radius, colors=cols, startangle=90, counterclock=False,
               wedgeprops=dict(width=0.22, edgecolor="black", linewidth=1.1))
        tot, acc = sum(sizes), 0.0
        for v, sz in zip(vals, sizes):
            ang = math.radians(90 - 360.0 * (acc + sz / 2) / tot)
            acc += sz
            ax.text((radius - 0.11) * math.cos(ang), (radius - 0.11) * math.sin(ang), "%.0f%%" % v, ha="center",
                    va="center", fontsize=7.6, fontweight="bold")
    ax.text(0, 0.07, "CTI", ha="center", va="center", fontsize=13, fontweight="bold")
    ax.text(0, -0.13, "outer ring: 671\ninner ring: 633", ha="center", va="center", fontsize=7.5, color=INK2)
    ax.set_title(title, fontsize=10.5)
fig.legend(handles=[plt.Rectangle((0, 0), 1, 1, fc=c, ec="black", lw=0.8, label="%d %%" % p) for c, p in zip(cols, P)],
           title="DG penetration", loc="center right", frameon=False, fontsize=9)
fig.suptitle("Percentage variation of the CTI with DG penetration - without and with the DSDR (each ring = 100 %)",
             fontsize=9.5, x=0.01, ha="left")
fig.tight_layout(rect=(0, 0, 0.9, 0.94))
fig.savefig(os.path.join(RES, "Fig07_DSDR_ring.png"), dpi=160)
plt.close(fig)

# ---- CTI and margin in ms ----------------------------------------------------------------------
fig, axes = plt.subplots(1, 3, figsize=(14, 4.2))
panels = ((axes[0], "633", cti, "Node 633: CTI = t_MMT(F633) - t_fast(R1)"),
          (axes[1], "633", marg, "Node 633: margin to the last fast trip (R1 and R2)"),
          (axes[2], "671", cti, "Node 671 (fault at 684): CTI = t_MMT(F671-2) - t_fast(R2)"))
for ax, n, data, title in panels:
    for s, c, lab in (("conv", ORANGE, "without DSDR"), ("dsdr", BLUE, "with DSDR")):
        ys = [1000 * v if abs(v) < 1e6 else float("nan") for v in data[(s, n)]]
        ax.plot(P, ys, color=c, lw=2, marker="o", label=lab)
    ax.axhline(0, color=RED, lw=1, ls=":")
    ax.set_title(title, fontsize=9, loc="left")
    ax.set_xlabel("DG penetration (%)")
    ax.set_ylabel("ms")
    ax.grid(True, color=GRID, lw=0.6)
    ax.legend(frameon=False, fontsize=8)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
fig.tight_layout()
fig.savefig(os.path.join(RES, "CTI_conventional_vs_DSDR.png"), dpi=160)
plt.close(fig)

# ---- summary --------------------------------------------------------------------------------------
L = ["# CTI against DG penetration: without and with the DSDR\n",
     "Seven PowerFactory models per scheme (DG at 0 ... 100 % of 4.05 MVA). Without DSDR: single-setting R2, fuses of "
     "the design without DG (F633 250E). With DSDR: R2 forward and reverse groups, fuses revised for the DSDR "
     "(F633 400E, F671-2 unchanged 300E). Times are PowerFactory's own relay and fuse times.\n",
     "| DG | 633 CTI vs R1, without / with DSDR (ms) | 633 margin to last fast trip, without / with (ms) | "
     "671 CTI vs R2, without / with (ms) |", "|---|---|---|---|"]
ms = lambda v: "%+.0f" % (1000 * v) if abs(v) < 1e6 else "n/a"
for k, p in enumerate(P):
    L.append("| %d %% | %s / %s | %s / %s | %s / %s |" % (p, ms(cti[("conv", "633")][k]), ms(cti[("dsdr", "633")][k]),
                                                         ms(marg[("conv", "633")][k]), ms(marg[("dsdr", "633")][k]),
                                                         ms(cti[("conv", "671")][k]), ms(cti[("dsdr", "671")][k])))
open(os.path.join(RES, "Summary.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
