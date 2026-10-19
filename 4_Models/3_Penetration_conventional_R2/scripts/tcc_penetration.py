"""
Time-current characteristics (TCC) of the two Fig. 7 cases at every DG penetration level.

  633: fuse F633 (A055C250E) against R1 (IAC77B801A, 720 A, TDS 0.5 / 10), LLL fault at 633
  671: fuse F671-2 (A055C300E) against R2 (CDG34, plugs 300 / 600 A, TMS 0.1 / 1.0), LL fault at 684

The curves are the same at every level (the settings are not changed); what moves are the operating
points: the fuse at its own current (grid + DG), the recloser at its current (grid only).
Currents from results/penetration_results.json (PowerFactory); curves identical to PowerFactory's
library types (DSDR_Study/curves.py, checked against c:Ttrip within 1.2 %).

Writes results/TCC_penetration_overview.png, results/TCC_penetration_633.png, results/TCC_penetration_671.png.
"""

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "DSDR_Study"))
import step3_design_and_evaluate as S3          # noqa: E402  (curves only; main() is not run)

RES = os.path.join(HERE, "results")
D = {int(k): v for k, v in json.load(open(os.path.join(RES, "penetration_results.json"))).items()}
P = sorted(D)
CONV = json.load(open(os.path.join(os.path.dirname(HERE), "DSDR_Study", "results", "settings.json")))["conventional"]
INF = float("inf")
INK2, GRID, BLUE, FUSEC = "#55534e", "#d9d8d4", "#2a78d6", "#1baf7a"
LEVEL_COL = ["#0b3c5d", "#1f6f9f", "#3f9fc4", "#f2b134", "#ef7d22", "#d94a1e", "#9e1b12"]
CASES = {
    "633": dict(key="633 LLL", fuse="F633", rec="R1", title="LLL fault at 633: fuse F633 and recloser R1",
                fast=lambda i: S3.t_r1(i, CONV, "f"), slow=lambda i: S3.t_r1(i, CONV, "d"),
                rec_label="R1 IAC77B801A, pickup 720 A, TDS 0.5 / 10"),
    "671": dict(key="671 LL", fuse="F671-2", rec="R2", title="LL fault at 684 (lateral from 671): fuse F671-2 and recloser R2",
                fast=lambda i: S3.t_r2(i, CONV, "R2fw", "f"), slow=lambda i: S3.t_r2(i, CONV, "R2fw", "d"),
                rec_label="R2 CDG34, plugs 300 / 600 A, TMS 0.1 / 1.0"),
}
II = [10 ** (2 + k / 200.0) for k in range(501)]          # 100 A ... 31.6 kA


def curve(ax, fn, **kw):
    pts = [(i, fn(i)) for i in II]
    pts = [(i, t) for i, t in pts if t < INF and 0 < t < 1000]
    ax.plot([i for i, _ in pts], [t for _, t in pts], **kw)


def draw(ax, node, levels, legend=True, compact=False):
    c = CASES[node]
    fz = S3.FTYPE[CONV["fuses"][c["fuse"]]]
    mmt = [(i, fz.mmt(i)) for i in II if fz.mmt(i) < INF]
    tct = [(i, fz.tct(i)) for i in II if fz.tct(i) < INF]
    ax.fill_between([i for i, _ in mmt], [t for _, t in mmt], [fz.tct(i) for i, _ in mmt], color=FUSEC, alpha=0.18, lw=0)
    ax.plot([i for i, _ in mmt], [t for _, t in mmt], color=FUSEC, lw=1.6,
            label="%s %s: minimum melting" % (c["fuse"], CONV["fuses"][c["fuse"]].replace("A055C", "")))
    ax.plot([i for i, _ in tct], [t for _, t in tct], color=FUSEC, lw=1.2, ls="--", label="%s: total clearing" % c["fuse"])
    curve(ax, c["fast"], color=BLUE, lw=1.8, label=c["rec_label"].split(",")[0] + " fast")
    curve(ax, c["slow"], color=BLUE, lw=1.4, ls="--", label=c["rec_label"].split(",")[0] + " delayed")
    for p in levels:
        f = D[p]["faults"][c["key"]]
        col = LEVEL_COL[P.index(p)]
        i_f, i_r = f["I_fuse"], f["I_R1" if c["rec"] == "R1" else "I_R2"]
        t_f, t_r = f["t_fuse_MMT"], f["t_rec_fast"]
        ax.plot([i_f], [t_f], marker="s", ms=7, color=col, mec="white", mew=1.0, zorder=6)
        ax.plot([i_r], [t_r], marker="o", ms=7, color=col, mec="white", mew=1.0, zorder=6)
        # vertical short-circuit lines: the fuse and the recloser carry different currents with the DG
        ax.axvline(i_f, color=FUSEC if compact else col, lw=1.0 if compact else 0.6, ls="-." if compact else ":", alpha=0.9, zorder=3)
        ax.axvline(i_r, color=BLUE if compact else col, lw=1.0 if compact else 0.6, ls="-." if compact else ":", alpha=0.9, zorder=3)
        if compact:
            # operating times read off on the time axis, and the CTI between them
            xa = max(i_f, i_r) * 1.45
            for t_, c_, lab in ((t_f, FUSEC, "t_MMT"), (t_r, BLUE, "t_fast")):
                ax.plot([500, xa], [t_, t_], color=c_, lw=0.8, ls=":", zorder=3)
                ax.text(520, t_, "%s %.3f s" % (lab, t_), fontsize=6.4, color=c_,
                        va="bottom" if t_ >= max(t_f, t_r) else "top")
            col_cti = "#9e1b12" if t_f < t_r else "#1a1a1a"
            ax.annotate("", xy=(xa, t_f), xytext=(xa, t_r),
                        arrowprops=dict(arrowstyle="<->", color=col_cti, lw=1.2, shrinkA=0, shrinkB=0), zorder=7)
            ax.text(xa * 1.08, (t_f * t_r) ** 0.5, "CTI\n%+.0f ms" % (1000 * (t_f - t_r)), fontsize=7.2, va="center",
                    fontweight="bold", color=col_cti)
            # labels of the two vertical lines, staggered so that they do not overlap when the currents are close
            ax.text(i_f, 70, " I(%s) = %.0f A" % (c["fuse"], i_f), rotation=90, fontsize=6.6, color=FUSEC, va="top",
                    ha="right" if i_f < i_r else "left")
            ax.text(i_r, 3.0, " I(%s) = %.0f A" % (c["rec"], i_r), rotation=90, fontsize=6.6, color=BLUE, va="top",
                    ha="left" if i_f < i_r else "right")
        else:
            ax.plot([i_r, i_f], [t_r, t_f], color=col, lw=0.8, ls=":", zorder=5)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(500, 20000 if node == "633" else 12000)
    ax.set_ylim(0.01, 100)
    ax.grid(True, which="both", color=GRID, lw=0.5)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    if legend:
        ax.legend(fontsize=7.3, frameon=True, framealpha=0.92, loc="upper right")


# ---- overview: both cases, all levels ---------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(13, 5.4))
for ax, node in zip(axes, ("633", "671")):
    draw(ax, node, P)
    ax.set_title(CASES[node]["title"], fontsize=9.5, loc="left")
    ax.set_xlabel("Current (A at 4.16 kV)")
axes[0].set_ylabel("Time (s)")
handles = [plt.Line2D([], [], marker="s", ls="", color=c, label="%d %%" % p) for c, p in zip(LEVEL_COL, P)]
handles += [plt.Line2D([], [], marker="s", ls="", color=INK2, label="fuse operating point"),
            plt.Line2D([], [], marker="o", ls="", color=INK2, label="recloser operating point")]
fig.legend(handles=handles, title="DG penetration", loc="center right", frameon=False, fontsize=8.5)
fig.tight_layout(rect=(0, 0, 0.88, 1))
fig.savefig(os.path.join(RES, "TCC_penetration_overview.png"), dpi=160)
plt.close(fig)

# ---- one panel per level ------------------------------------------------------------------------
for node in ("633", "671"):
    fig, axes = plt.subplots(2, 4, figsize=(15, 7.6), sharex=True, sharey=True)
    for k, ax in enumerate(axes.flat):
        if k >= len(P):
            ax.axis("off")
            h, l = axes.flat[0].get_legend_handles_labels()
            ax.legend(h, l, loc="center", fontsize=8, frameon=False)
            continue
        draw(ax, node, [P[k]], legend=False, compact=True)
        ax.set_title("DG penetration %d %% (%.2f MVA)" % (P[k], 4.05 * P[k] / 100), fontsize=9.5, loc="left")
    for ax in axes[1]:
        ax.set_xlabel("Current (A)")
    for ax in axes[:, 0]:
        ax.set_ylabel("Time (s)")
    fig.tight_layout()
    fig.savefig(os.path.join(RES, "TCC_penetration_%s.png" % node), dpi=140)
    plt.close(fig)
print("written: TCC_penetration_overview.png, TCC_penetration_633.png, TCC_penetration_671.png")
