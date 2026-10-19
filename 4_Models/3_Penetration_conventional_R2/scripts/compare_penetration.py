"""
Comparative results of the penetration study: pickups (eq. 3 / eq. 12) and short-circuit levels.

Pickup per level: I_p = 1.25 x I_nom, I_nom = largest phase current of the recloser in that level's load
flow, then the nearest tap of the relay (IAC77B801A on CT 900/5; CDG34 on CT 1000/5 forward, 500/5
reverse).  Compared with the setting actually in the models (the design without DG).

Writes results/Pickup_vs_penetration.csv, results/SC_levels_vs_penetration.csv,
results/Ifmin_vs_pickup.csv, results/Fig_pickup_sc.png and results/Comparison_summary.md.
"""

import csv
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
D = {int(k): v for k, v in json.load(open(os.path.join(RES, "penetration_results.json"))).items()}
P = sorted(D)
OLF = 1.25
IAC_TAPS = [0.5, 0.6, 0.7, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 4.0]
CDG_TAPS = [1.0, 1.2, 1.5, 2.0, 2.4, 3.0, 4.0]
SET = dict(R1=720.0, R2_fast=300.0, R2_del=600.0)               # settings in the models (design without DG)


def tap(target, taps, ratio):
    return min(taps, key=lambda t: abs(t * ratio - target)) * ratio


L = ["# Penetration study - pickups and short-circuit levels\n"]

# ---- pickups ----------------------------------------------------------------------------------
pk = []
for p in P:
    l = D[p]["loadflow"]
    rev = l["R2_P_kW"] < 0
    ip1, ip2 = OLF * l["R1_A"], OLF * l["R2_A"]
    r2_ratio = (500.0 if rev else 1000.0) / 5
    pk.append(dict(p=p, i1=l["R1_A"], ip1=ip1, tap1=tap(ip1, IAC_TAPS, 180.0), i2=l["R2_A"], dir2="reverse" if rev else "forward",
                   P2=l["R2_P_kW"], ip2=ip2, tap2f=tap(ip2 / 2, CDG_TAPS, r2_ratio), tap2d=tap(ip2, CDG_TAPS, r2_ratio)))
with open(os.path.join(RES, "Pickup_vs_penetration.csv"), "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["DG penetration %", "R1 Inom (A)", "R1 Ip = 1.25 Inom (A)", "R1 nearest tap (A)", "R1 set in model (A)",
                "R2 Inom (A)", "R2 load direction", "R2 P (kW)", "R2 Ip = 1.25 Inom (A)", "R2 plugs fast / delayed (A)",
                "R2 set in model fast / delayed (A)"])
    for r in pk:
        w.writerow([r["p"], r["i1"], "%.1f" % r["ip1"], "%.0f" % r["tap1"], SET["R1"], r["i2"], r["dir2"], r["P2"],
                    "%.1f" % r["ip2"], "%.0f / %.0f" % (r["tap2f"], r["tap2d"]), "%.0f / %.0f" % (SET["R2_fast"], SET["R2_del"])])
L.append("## 1. Pickup currents (eq. 3, OLF = 1.25)\n")
L.append("The models keep the pickups of the design without DG (R1 720 A; R2 forward plugs 300 / 600 A). "
         "The table shows what eq. (3) would give from each level's own load flow.\n")
L.append("| DG | R1 Inom (A) | R1 1.25 Inom (A) | R1 tap (A) | R2 Inom (A) | R2 load flow | R2 1.25 Inom (A) | R2 plugs fast / delayed (A) |")
L.append("|---|---|---|---|---|---|---|---|")
for r in pk:
    L.append("| %d %% | %.1f | %.1f | %.0f | %.1f | %s (%+.0f kW) | %.1f | %.0f / %.0f%s |" % (
        r["p"], r["i1"], r["ip1"], r["tap1"], r["i2"], r["dir2"], r["P2"], r["ip2"], r["tap2f"], r["tap2d"],
        " (CT 500/5)" if r["dir2"] == "reverse" else ""))
L.append("\nSet in the models: R1 720 A, R2 300 / 600 A at every level.\n")

# ---- short-circuit levels ---------------------------------------------------------------------
path = os.path.join(RES, "sc_levels.json")
if os.path.isfile(path):
    S = {int(k): v for k, v in json.load(open(path)).items()}
    # Direction at R2 from the topology: with the DG at 692 R2 carries only the DG's current, towards 632,
    # for faults on the grid side of R2 (R1's zone), and the grid's current, towards 671, for faults beyond
    # it.  (The active power at R2 during a fault is not a reliable direction signal: the fault current is
    # mostly reactive.)
    R1_ZONE = {"632", "633", "634", "645", "646", "DL"}
    for rows_ in S.values():
        for r in rows_:
            r["R2_dir"] = "-" if r["I_R2"] < 1.0 else ("rev" if r["node"] in R1_ZONE else "fwd")
    nodes = []
    for r in S[0]:
        if r["node"] not in nodes:
            nodes.append(r["node"])

    def best(p, node, case="max", key="I_fault"):
        rows = [r for r in S[p] if r["node"] == node and r["case"] == case]
        return max(rows, key=lambda r: r[key]) if rows else None

    with open(os.path.join(RES, "SC_levels_vs_penetration.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Node", "Fault (largest)"] + ["If,max %d %% (A)" % p for p in P] + ["change 0 -> 100 %"]
                   + ["I R1 %d %% (A)" % p for p in P] + ["I R2 %d %% (A)" % p for p in P] + ["R2 direction at 100 %"])
        L.append("## 2. Maximum short-circuit level at each node (bolted, largest fault type), A\n")
        L.append("| Node | Fault | " + " | ".join("%d %%" % p for p in P) + " | change |")
        L.append("|---|---|" + "---|" * (len(P) + 1))
        for n in nodes:
            b = [best(p, n) for p in P]
            w.writerow([n, "%s %s" % (b[-1]["type"], b[-1]["phases"])] + ["%.0f" % x["I_fault"] for x in b]
                       + ["%+.0f %%" % (100 * (b[-1]["I_fault"] / b[0]["I_fault"] - 1))]
                       + ["%.0f" % x["I_R1"] for x in b] + ["%.0f" % x["I_R2"] for x in b] + [b[-1]["R2_dir"]])
            L.append("| %s | %s | %s | %+.0f %% |" % (n, b[-1]["type"], " | ".join("%.0f" % x["I_fault"] for x in b),
                                                     100 * (b[-1]["I_fault"] / b[0]["I_fault"] - 1)))
        L.append("\n## 3. Current through the reclosers for the same faults, A (0 % -> 100 %)\n")
        L.append("| Node | R1 at 0 % | R1 at 100 % | R1 change | R2 at 0 % | R2 at 100 % | R2 direction at 100 % |")
        L.append("|---|---|---|---|---|---|---|")
        for n in nodes:
            a, z = best(0, n), best(100, n)
            L.append("| %s | %.0f | %.0f | %+.0f %% | %.0f | %.0f | %s |" % (n, a["I_R1"], z["I_R1"], 100 * (z["I_R1"] / a["I_R1"] - 1),
                                                                      a["I_R2"], z["I_R2"], z["R2_dir"]))

    # minimum fault (LG through 3 ohm) seen by each recloser in its zone, against the pickup
    zone1 = [n for n in nodes if n in ("632", "633", "645", "646", "DL", "671", "692", "675", "680", "684", "611", "652")]
    zone2 = [n for n in nodes if n in ("671", "692", "675", "680", "684", "611", "652")]
    rows = []
    for p in P:
        m1 = min((r for r in S[p] if r["case"] == "min" and r["node"] in zone1), key=lambda r: r["I_R1"])
        m2 = min((r for r in S[p] if r["case"] == "min" and r["node"] in zone2), key=lambda r: r["I_R2"])
        rows.append((p, m1, m2))
    with open(os.path.join(RES, "Ifmin_vs_pickup.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["DG penetration %", "lowest R1 current, LG 3 ohm (A)", "at node", "R1 pickup (A)", "R1 sees it?",
                    "lowest R2 current in its zone, LG 3 ohm (A)", "at node", "R2 fast pickup (A)", "R2 sees it?"])
        L.append("\n## 4. Minimum fault (LG through 3 ohm) against the pickup\n")
        L.append("Lowest current through each recloser for an LG fault through 3 ohm anywhere in its zone. R2's fast curve "
                 "starts at 2 x 300 A = 600 A (CDG curve starts at twice the plug).\n")
        L.append("| DG | R1 lowest (A) | node | R1 pickup 720 A | R2 lowest (A) | node | R2 fast start 600 A |")
        L.append("|---|---|---|---|---|---|---|")
        for p, m1, m2 in rows:
            ok1, ok2 = m1["I_R1"] >= 1.5 * SET["R1"], m2["I_R2"] >= 2 * SET["R2_fast"]
            w.writerow([p, m1["I_R1"], m1["node"], SET["R1"], "yes" if ok1 else "NO", m2["I_R2"], m2["node"], 2 * SET["R2_fast"], "yes" if ok2 else "NO"])
            L.append("| %d %% | %.0f | %s | %s | %.0f | %s | %s |" % (p, m1["I_R1"], m1["node"], "operates" if ok1 else "**does not operate**",
                                                                 m2["I_R2"], m2["node"], "operates" if ok2 else "**does not operate**"))
        L.append("\nR1's IAC curve starts at 1.5 x pickup = 1080 A, so R1 already misses the 3-ohm LG fault at 680 by 6 A "
                 "without DG (1074 A); the margin then grows to 503 A short at 100 %. R2 still sees its zone's minimum fault "
                 "up to 50 % (606 A against 600 A) and loses it just above 50 %.\n")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    ax = axes[0]
    for n, c in zip(nodes, plt.cm.tab20.colors):
        ax.plot(P, [best(p, n)["I_fault"] / 1000 for p in P], marker="o", ms=4, lw=1.5, color=c, label=n)
    ax.set_title("Maximum fault level at each node", fontsize=10, loc="left")
    ax.set_xlabel("DG penetration (%)")
    ax.set_ylabel("If,max (kA)")
    ax.legend(ncol=2, fontsize=7, frameon=False)
    ax = axes[1]
    ax.plot(P, [r["ip1"] for r in pk], color="#2a78d6", lw=2, marker="o", label="R1: 1.25 x Inom from load flow")
    ax.axhline(SET["R1"], color="#2a78d6", ls="--", lw=1.2, label="R1 set: 720 A")
    ax.plot(P, [r["ip2"] for r in pk], color="#eb6834", lw=2, marker="o", label="R2: 1.25 x Inom (reverse at 100 %)")
    ax.axhline(SET["R2_del"], color="#eb6834", ls="--", lw=1.2, label="R2 set: 600 A (delayed plug)")
    ax.plot(P, [m1["I_R1"] for _, m1, _ in rows], color="#2a78d6", lw=1.2, ls=":", marker="s", ms=4, label="R1 lowest LG 3 ohm current")
    ax.plot(P, [m2["I_R2"] for _, _, m2 in rows], color="#eb6834", lw=1.2, ls=":", marker="s", ms=4, label="R2 lowest LG 3 ohm current")
    ax.set_title("Pickup against load current and minimum fault current", fontsize=10, loc="left")
    ax.set_xlabel("DG penetration (%)")
    ax.set_ylabel("Current (A)")
    ax.legend(fontsize=7, frameon=False)
    for a in axes:
        a.grid(True, color="#d9d8d4", lw=0.6)
        for sp in ("top", "right"):
            a.spines[sp].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(RES, "Fig_pickup_sc.png"), dpi=160)
    plt.close(fig)
else:
    L.append("Short-circuit levels: run sc_levels_penetration.py first (PowerFactory closed).\n")

open(os.path.join(RES, "Comparison_summary.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
