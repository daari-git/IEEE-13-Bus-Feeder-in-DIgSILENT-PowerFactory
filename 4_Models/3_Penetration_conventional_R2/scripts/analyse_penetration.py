"""
Analysis of the DG penetration study (Fig. 7) from results/penetration_results.json.

CTI = t_MMT(fuse) - t_fast(recloser), both from PowerFactory's own fuse and relay elements.
Fig. 7 is a doughnut chart, so every ring adds up to 100 %:
    CTI %  =  100 x CTI(p) / sum over the seven levels of |CTI|     (sign kept)

Writes results/Penetration_CTI.csv, results/Penetration_loadflow.csv, results/Fig07_penetration.png,
results/Fig07_penetration_currents.png and results/Penetration_summary.md.
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
CMP = os.path.join(HERE, "comparison")          # the reference paper's values, for the comparison only
os.makedirs(CMP, exist_ok=True)
D = {int(k): v for k, v in json.load(open(os.path.join(RES, "penetration_results.json"))).items()}
P = sorted(D)
PAPER = {"633": [30, 23, 14, 6, -4, -9, -16], "671": [36, 22, 12, 6, 0, -8, -14]}   # read from Fig. 7
CASE = {"633": "633 LLL", "671": "671 LL"}
INK, INK2, GRID, BLUE, ORANGE, RED = "#1a1a1a", "#55534e", "#d9d8d4", "#2a78d6", "#eb6834", "#d03b3b"


def f(p, node):
    return D[p]["faults"][CASE[node]]


cti = {n: [f(p, n)["CTI_s"] for p in P] for n in CASE}
ring = {n: [100.0 * c / sum(abs(x) for x in cti[n]) for c in cti[n]] for n in CASE}

# ---- tables -----------------------------------------------------------------------------------
with open(os.path.join(RES, "Penetration_CTI.csv"), "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["DG penetration %", "DG rating (MVA)",
                "633: I F633 (A)", "633: I R1 (A)", "633: F633 t_MMT (s)", "633: R1 fast (s)", "633: CTI (s)", "633: CTI ring %",
                "671: I F671-2 (A)", "671: I R2 (A)", "671: F671-2 t_MMT (s)", "671: R2 fast (s)", "671: CTI (s)", "671: CTI ring %"])
    for k, p in enumerate(P):
        a, b = f(p, "633"), f(p, "671")
        w.writerow([p, D[p]["loadflow"]["dg_rating_MVA"],
                    a["I_fuse"], a["I_R1"], "%.4f" % a["t_fuse_MMT"], "%.4f" % a["t_rec_fast"], "%+.4f" % a["CTI_s"], "%+.1f" % ring["633"][k],
                    b["I_fuse"], b["I_R2"], "%.4f" % b["t_fuse_MMT"], "%.4f" % b["t_rec_fast"], "%+.4f" % b["CTI_s"], "%+.1f" % ring["671"][k]])
with open(os.path.join(CMP, "Penetration_CTI_vs_paper.csv"), "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["DG penetration %", "633 CTI ring % (model)", "633 paper %", "671 CTI ring % (model)", "671 paper %"])
    for k, p in enumerate(P):
        w.writerow([p, "%+.1f" % ring["633"][k], PAPER["633"][k], "%+.1f" % ring["671"][k], PAPER["671"][k]])
with open(os.path.join(RES, "Penetration_loadflow.csv"), "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["DG penetration %", "DG P (MW)", "R1 current (A)", "R1 P (kW)", "R2 current (A)", "R2 P (kW, + towards 671)",
                "V633 a/b/c (pu)", "V671 a/b/c (pu)", "V684 a/c (pu)"])
    for p in P:
        l = D[p]["loadflow"]
        w.writerow([p, l["dg_P_MW"], l["R1_A"], l["R1_P_kW"], l["R2_A"], l["R2_P_kW"], " / ".join("%.4f" % v for v in l["V"]["633"]),
                    " / ".join("%.4f" % v for v in l["V"]["671"]), "%.4f / %.4f" % (l["V"]["684"][0], l["V"]["684"][2])])

# ---- Fig. 7 (doughnut) ------------------------------------------------------------------------
cols = ["#0070c0", "#bfbfbf", "#ffd500", "#ffa600", "#4472c4", "#c00000", "#ff3b30"]


def doughnut(panels, path, width):
  fig, axes = plt.subplots(1, len(panels), figsize=(width, 5.4), squeeze=False)
  for ax, (data, title) in zip(axes[0], panels):
    for node, radius in (("671", 1.0), ("633", 0.76)):
        vals = data[node]
        sizes = [max(abs(v), 0.5) for v in vals]
        ax.pie(sizes, radius=radius, colors=cols, startangle=90, counterclock=False,
               wedgeprops=dict(width=0.22, edgecolor="black", linewidth=1.1))
        tot, acc = sum(sizes), 0.0
        for v, s in zip(vals, sizes):
            ang = math.radians(90 - 360.0 * (acc + s / 2) / tot)
            acc += s
            ax.text((radius - 0.11) * math.cos(ang), (radius - 0.11) * math.sin(ang), "%.0f%%" % v,
                    ha="center", va="center", fontsize=7.6, fontweight="bold")
    ax.text(0, 0.07, "CTI", ha="center", va="center", fontsize=13, fontweight="bold")
    ax.text(0, -0.13, "outer ring: 671 (external)\ninner ring: 633 (internal)", ha="center", va="center", fontsize=7.5, color=INK2)
    ax.set_title(title, fontsize=10.5)
  fig.legend(handles=[plt.Rectangle((0, 0), 1, 1, fc=c, ec="black", lw=0.8, label="%d %%" % p) for c, p in zip(cols, P)],
             title="DG penetration", loc="center right", frameon=False, fontsize=9)
  fig.tight_layout(rect=(0, 0, 0.82 if len(panels) == 1 else 0.9, 1))
  fig.savefig(path, dpi=160)
  plt.close(fig)


doughnut([(ring, "")], os.path.join(RES, "Fig07_penetration.png"), 7.0)
doughnut([(ring, "This study (PowerFactory)"), (PAPER, "Reference paper (values read from its Fig. 7)")],
         os.path.join(CMP, "Fig07_penetration_vs_paper.png"), 11.2)

# ---- why: currents and times against penetration ---------------------------------------------
fig, axes = plt.subplots(1, 3, figsize=(13, 4.0))
for ax, node, fuse, rec in ((axes[0], "633", "F633", "R1"), (axes[1], "671", "F671-2", "R2")):
    ax.plot(P, [f(p, node)["I_fuse"] for p in P], color=ORANGE, lw=2, marker="o", label="fuse %s (grid + DG)" % fuse)
    ax.plot(P, [f(p, node)["I_R1" if rec == "R1" else "I_R2"] for p in P], color=BLUE, lw=2, marker="o", label="recloser %s (grid only)" % rec)
    ax.plot(P, [f(p, node)["I_DG"] for p in P], color=INK2, lw=1.4, ls="--", marker="s", ms=4, label="DG contribution")
    ax.set_title("Fault %s: currents" % ("LLL at 633" if node == "633" else "LL at 684 (lateral from 671)"), fontsize=9.5, loc="left")
    ax.set_xlabel("DG penetration (%)")
    ax.set_ylabel("Current (A)")
    ax.legend(frameon=False, fontsize=7.6)
ax = axes[2]
for node, c, lab in (("633", BLUE, "633: F633 - R1 fast"), ("671", ORANGE, "671: F671-2 - R2 fast")):
    ax.plot(P, [1000 * x for x in cti[node]], color=c, lw=2, marker="o", label=lab)
ax.axhline(0, color=RED, lw=1, ls=":")
ax.text(100, 4, "CTI = 0: fuse saving lost below", color=INK2, fontsize=7.5, ha="right")
ax.set_title("CTI = t_MMT(fuse) - t_fast(recloser)", fontsize=9.5, loc="left")
ax.set_xlabel("DG penetration (%)")
ax.set_ylabel("CTI (ms)")
ax.legend(frameon=False, fontsize=7.6)
for a in axes:
    a.grid(True, color=GRID, lw=0.6)
    for sp in ("top", "right"):
        a.spines[sp].set_visible(False)
fig.tight_layout()
fig.savefig(os.path.join(RES, "Fig07_penetration_currents.png"), dpi=160)
plt.close(fig)


# ---- summary ------------------------------------------------------------------------------------
def zero_cross(vals):
    for (p1, v1), (p2, v2) in zip(zip(P, vals), zip(P[1:], vals[1:])):
        if v1 > 0 >= v2:
            return p1 + (p2 - p1) * v1 / (v1 - v2)
    return None


L = []
L.append("# DG penetration study - Fig. 7\n")
L.append("Seven PowerFactory models (`pfd/IEEE13_DG_penetration_000.pfd` ... `_100.pfd`), copies of the main project "
         "with the DG at 692 set to 0 ... 100 % of 4.05 MVA and the conventional (single-setting) protection. "
         "The main project itself was not changed. Times are PowerFactory's own relay and fuse times.\n")
L.append("| DG | DG MVA | 633: I F633 / I R1 (A) | 633: CTI (s) | 633 ring % | 671: I F671-2 / I R2 (A) | 671: CTI (s) | 671 ring % |")
L.append("|---|---|---|---|---|---|---|---|")
for k, p in enumerate(P):
    a, b = f(p, "633"), f(p, "671")
    L.append("| %d %% | %.2f | %.0f / %.0f | %+.3f | %+.1f | %.0f / %.0f | %+.3f | %+.1f |" % (
        p, D[p]["loadflow"]["dg_rating_MVA"], a["I_fuse"], a["I_R1"], a["CTI_s"], ring["633"][k],
        b["I_fuse"], b["I_R2"], b["CTI_s"], ring["671"][k]))
L.append("\nRing %% = 100 x CTI / sum of |CTI| over the seven levels (each ring adds up to 100 %%). "
         "Sum of |CTI|: 633 %.3f s, 671 %.3f s.\n" % (sum(abs(x) for x in cti["633"]), sum(abs(x) for x in cti["671"])))
z633, z671 = zero_cross(cti["633"]), zero_cross(cti["671"])
L.append("Zero crossing of the CTI: 633 at about %s, 671 %s.\n" % (
    "%.0f %% penetration" % z633 if z633 else "-", "at about %.0f %%" % z671 if z671 else "not reached up to 100 %"))
open(os.path.join(RES, "Penetration_summary.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
