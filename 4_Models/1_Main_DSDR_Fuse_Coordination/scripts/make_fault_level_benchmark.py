"""
Fault levels of the model against the IEEE 13-node short-circuit benchmark (Kersting & Shirek, as quoted by
the same authors in their 2020 paper) and against the reference paper's Table II.

Output: results/figures/Fault_level_benchmark.png and results/Fault_level_benchmark.csv
"""

import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from protection_data import PAPER_TABLE2

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
BENCH = {"632": 4.80, "633": 4.15, "645": 3.41, "646": 3.05, "671": 3.35, "692": 3.35, "675": 3.12,
         "680": 2.91, "684": 2.62, "652": 1.79, "611": 1.85}          # kA (634, 0.48 kV side, left out of the chart)
PAPER_BRANCH = {"632": ("RG60", "632"), "633": ("632", "633"), "645": ("632", "645"), "646": ("645", "646"),
                "671": ("632", "671"), "692": ("671", "692"), "675": ("692", "675"), "680": ("671", "680"),
                "684": ("671", "684"), "652": ("684", "652"), "611": ("684", "611")}


def main():
    ours = {r["Bus"]: float(r["If,max without DG (A)"]) / 1000.0
            for r in csv.DictReader(open(os.path.join(RES, "database", "Comparison_fault_current.csv")))}
    nodes = list(BENCH)
    rows = []
    for n in nodes:
        paper = PAPER_TABLE2[PAPER_BRANCH[n]][2]
        rows.append([n, BENCH[n], round(ours[n], 2), round(100 * (ours[n] - BENCH[n]) / BENCH[n], 1), paper,
                     round(100 * (paper - BENCH[n]) / BENCH[n], 1)])
    with open(os.path.join(RES, "Fault_level_benchmark.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Node", "IEEE benchmark (kA)", "This study (kA)", "Study vs benchmark (%)",
                    "Paper Table II If,max of the branch (kA)", "Paper vs benchmark (%)"])
        w.writerows(rows)

    fig, ax = plt.subplots(figsize=(9.6, 4.6))
    x = range(len(nodes))
    wd = 0.27
    b1 = ax.bar([i - wd for i in x], [r[1] for r in rows], wd, color="#1b3755", label="IEEE benchmark")
    b2 = ax.bar(list(x), [r[2] for r in rows], wd, color="#2f9e6a", label="This study (PowerFactory)")
    b3 = ax.bar([i + wd for i in x], [r[4] for r in rows], wd, color="#e07b39", label="Reference paper, Table II (branch If,max)")
    for bars in (b2, b3):
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.08, "%.2f" % b.get_height(), ha="center",
                    va="bottom", fontsize=6.6, rotation=90)
    ax.axhline(4.80, color="#1b3755", lw=0.8, ls=":")
    ax.text(len(nodes) - 0.5, 4.86, "feeder head (632), benchmark 4.80 kA", ha="right", fontsize=8, color="#1b3755")
    ax.set_xticks(list(x))
    ax.set_xticklabels(nodes)
    ax.set_xlabel("Node")
    ax.set_ylabel("Maximum fault current (kA), DG out")
    ax.set_ylim(0, 9.2)
    ax.legend(loc="upper left", fontsize=9, frameon=False, ncol=3)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.grid(axis="y", color="#d9d8d4", lw=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    out = os.path.join(RES, "figures", "Fault_level_benchmark.png")
    fig.savefig(out, dpi=170)
    plt.close(fig)
    for r in rows:
        print(r)
    print("max |study - benchmark| = %.1f %%" % max(abs(r[3]) for r in rows))
    return rows


if __name__ == "__main__":
    main()
