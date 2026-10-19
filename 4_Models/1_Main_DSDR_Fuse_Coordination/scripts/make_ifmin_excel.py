"""
Excel workbook of the minimum-fault-current calculation (If,min, DG out), from the PowerFactory database:

  1 Method          how the faults were calculated and how If,min is chosen
  2 LG_3ohm_faults  every LG fault through 3 ohm (node, phase): current at the fault, through R1 and R2,
                    and whether the node is in the zone of R1 / R2
  3 If_min_R1_R2    If,min of each recloser zone (values, and the Excel formula for each), the current at the
                    farthest node, the pickup and the check  Ip < If,min
  4 All_sections    If,min of every protected section (Table II of the report)

Input : results/database/5_ShortCircuit_DG_out.csv, results/database/Ifmin_DG_out.csv
Output: results/database/Minimum_Fault_Current_Calculation.xlsx
"""

import csv
import os

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from protection_data import TABLE2_BRANCHES

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "results", "database")
OUT = os.path.join(DB, "Minimum_Fault_Current_Calculation.xlsx")

ZONES = {"R1": next(b[4] for b in TABLE2_BRANCHES if b[0] == "RG60"),
         "R2": next(b[4] for b in TABLE2_BRANCHES if (b[0], b[1]) == ("632", "671"))}
PICKUP = {"R1": ("CT 900/5, tap 4 A", 720.0, 587.7), "R2": ("CT 1000/5, fast plug 300 A (curve from 600 A)", 600.0, 470.0)}
FARTHEST = {"R1": "652", "R2": "652"}

THIN = Side(style="thin", color="000000")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEAD = Font(bold=True)
HFILL = PatternFill("solid", fgColor="DDEBF7")
KEY = PatternFill("solid", fgColor="FFF2CC")


def grid(ws, r0, rows, widths=None, header=True):
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            c = ws.cell(row=r0 + i, column=j + 1, value=v)
            if isinstance(v, str) and v.startswith("="):
                c.data_type = "s"                       # show the formula as text, do not evaluate it
            c.border = BOX
            c.alignment = Alignment(vertical="center", wrap_text=True)
            if header and i == 0:
                c.font, c.fill = HEAD, HFILL
    if widths:
        for j, w in enumerate(widths):
            ws.column_dimensions[get_column_letter(j + 1)].width = w


def farthest(wb, sc):
    """Sheet: line distance from each recloser to every node of its zone (from the model's line lengths),
    and the lowest LG 3-ohm current through the recloser for a fault at that node."""
    import json
    path = os.path.join(DB, "Zone_distances.json")
    if not os.path.exists(path):
        return
    zd = json.load(open(path))
    ws = wb.create_sheet("Farthest_node")
    ws["A1"] = "Farthest node of each recloser zone, and where the minimum fault current really is (DG out)"
    ws["A1"].font = Font(bold=True, size=13)
    r0 = 3
    for dev, col in (("R1", "R1 current (A)"), ("R2", "R2 current (A)")):
        dist = zd[dev]["dist"]
        rows = [["Node (zone of %s)" % dev, "Line length from %s (ft)" % zd[dev]["start"], "Fault current at the node, "
                 "lowest phase (A)", "Current through %s, lowest phase (A)" % dev, "Remark"]]
        far = max(dist, key=dist.get)
        lows = {}
        for n in sorted(dist, key=dist.get):
            recs = [r for r in sc if r["Faulted bus"] == n]
            low = min(recs, key=lambda r: float(r[col]))
            lows[n] = float(low[col])
            rows.append([n, dist[n], round(min(float(r["Fault current (A)"]) for r in recs), 1), "%.1f (phase %s)" % (
                float(low[col]), low["Phases"]), ""])
        lowest = min(lows, key=lows.get)
        for row in rows[1:]:
            notes = []
            if row[0] == far:
                notes.append("farthest node")
            if row[0] == lowest:
                notes.append("lowest recloser current = If,min")
            row[4] = "; ".join(notes)
        grid(ws, r0, rows, [18, 30, 30, 30, 32])
        for i, row in enumerate(rows[1:], r0 + 1):
            if row[4]:
                for c in range(1, 6):
                    ws.cell(row=i, column=c).fill = KEY
        r0 += len(rows) + 2
    notes = [
        "Farthest node: largest line length from the recloser to a node of its zone, from the line lengths of the "
        "PowerFactory model (feet). R1: from RG60 at the feeder head; R2: from its position at the 671 end of line 632-671.",
        "R1: 650-632 2000 + 632-671 2000 + 671-684 300 + 684-652 800 = 5100 ft to node 652.",
        "R2: 671-684 300 + 684-652 800 = 1100 ft to node 652.",
        "The method takes If,min as the LG fault through 3 ohm at the farthest node (652). Because the recloser also "
        "carries the load current of its phase, the lowest recloser current is found at 680 (phase B): 1074.4 A at R1 "
        "and 878.5 A at R2. The pickups are checked against these lowest values, which is the safer choice.",
    ]
    for k, t in enumerate(notes):
        c = ws.cell(row=r0 + k, column=1, value=t)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(start_row=c.row, start_column=1, end_row=c.row, end_column=5)
        ws.row_dimensions[c.row].height = 32


def hand_check(wb):
    """Sheet 5: hand calculation of the If,min case (LG through 3 ohm at 680, phase B, DG out) with symmetrical
    components and superposition, against PowerFactory.  Data: results/database/Ifmin_validation.json
    (written by validate_ifmin.py)."""
    import cmath
    import json
    import math
    path = os.path.join(DB, "Ifmin_validation.json")
    if not os.path.exists(path):
        return
    d = json.load(open(path))
    rad = math.radians
    P = lambda m, a: cmath.rect(m, rad(a))
    fmt = lambda z: "%.1f A at %.1f deg" % (abs(z), math.degrees(cmath.phase(z)))
    zc = d["Z_at_680_candidates"]
    z1, z2, z0 = complex(zc["m:R1"], zc["m:X1"]), complex(zc["m:R2"], zc["m:X2"]), complex(zc["m:R0"], zc["m:X0"])
    vb = P(1000 * d["V_pre_680"]["B"][0], d["V_pre_680"]["B"][1])
    ztot = z1 + z2 + z0 + 3 * 3.0
    i_f = 3 * vb / ztot
    i_f_pf = d["I_fault_680"]["B"]
    l1 = P(d["I_load_R1"]["B"][0] / 1000, d["I_load_R1"]["B"][1])
    l2 = P(d["I_load_R2"]["B"][0] / 1000, d["I_load_R2"]["B"][1])
    f1, f2 = d["I_fault_R1"]["B"], d["I_fault_R2"]["B"]
    if_pf = P(i_f_pf, d["I_fault_680_angle_candidates"].get("m:phii:B", 0.0))
    r1, r2 = l1 + if_pf, l2 + if_pf
    pct = lambda a, b: "%+.1f %%" % (100 * (a - b) / b)

    ws = wb.create_sheet("Hand_check")
    ws["A1"] = "Hand calculation of If,min: LG fault through Rf = 3 ohm at node 680, phase B, DG out of service"
    ws["A1"].font = Font(bold=True, size=13)
    rows = [["Step", "Formula", "Values", "Result (hand)", "PowerFactory", "Difference"],
            ["1  Thevenin sequence impedances at 680", "Z1, Z2, Z0 seen from the fault (PowerFactory, DG out)",
             "Z1 = Z2 = %.4f + j%.4f ohm;  Z0 = %.4f + j%.4f ohm" % (z1.real, z1.imag, z0.real, z0.imag), "", "", ""],
            ["2  Pre-fault voltage, phase B at 680", "V_B from the load flow (complete method keeps it)",
             "%.1f V at %.2f deg (%.3f pu; regulator boost)" % (abs(vb), d["V_pre_680"]["B"][1], d["V_pre_680"]["B"][2]),
             "", "", ""],
            ["3  Total loop impedance", "Z = Z1 + Z2 + Z0 + 3 Rf",
             "%.4f + j%.4f + 9" % ((z1 + z2 + z0).real, (z1 + z2 + z0).imag),
             "%.3f + j%.3f = %.3f ohm at %.1f deg" % (ztot.real, ztot.imag, abs(ztot), math.degrees(cmath.phase(ztot))),
             "", ""],
            ["4  Fault current at 680 (LG)", "I_f = 3 V_B / (Z1 + Z2 + Z0 + 3 Rf)",
             "3 x %.1f / %.3f" % (abs(vb), abs(ztot)), fmt(i_f), "%.1f A at %.1f deg" % (abs(if_pf), math.degrees(cmath.phase(if_pf))),
             pct(abs(i_f), abs(if_pf))],
            ["5  Load current through R2, phase B", "from the load flow (before the fault)", "", fmt(l2), "", ""],
            ["6  Current through R2, phase B, during the fault", "I_R2 = I_load,R2 + I_f   (superposition; the "
             "feeder is radial, so all of I_f passes R2)", "%s + %s" % (fmt(l2), fmt(if_pf)), fmt(r2), "%.1f A" % f2[0],
             pct(abs(r2), f2[0])],
            ["7  Load current through R1, phase B", "from the load flow (before the fault)", "", fmt(l1), "", ""],
            ["8  Current through R1, phase B, during the fault", "I_R1 = I_load,R1 + I_f   (all of I_f also passes R1)",
             "%s + %s" % (fmt(l1), fmt(if_pf)), fmt(r1), "%.1f A" % f1[0], pct(abs(r1), f1[0])]]
    grid(ws, 3, rows, [34, 44, 48, 30, 18, 12])
    notes = [
        "Why phase B gives the minimum: phase B carries the smallest load current at R1 (411 A, against 558 A on phase A "
        "and 588 A on phase C), so load + fault current is smallest on phase B.",
        "Why the R1 hand value is about 3.5 % high: superposition with the PRE-FAULT load current assumes the loads keep "
        "drawing the same current. During the fault the phase-B voltage sags, the loads supplied through R1 draw less, "
        "and PowerFactory's complete method includes that. R1 feeds more load (632, 633, 645, 646, DL and the R2 zone) "
        "than R2, so the effect is larger at R1; at R2 the hand value is within 0.5 %.",
        "Result: the hand calculation confirms the PowerFactory values If,min(R1) = 1074 A and If,min(R2) = 879 A "
        "within the accuracy of superposition.",
        "Note: the R2 value is 878.5 A (rounded 879 A).",
    ]
    for k, t in enumerate(notes):
        c = ws.cell(row=3 + len(rows) + 1 + k, column=1, value=t)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(start_row=c.row, start_column=1, end_row=c.row, end_column=6)
        ws.row_dimensions[c.row].height = 32
    for r in range(4, 3 + len(rows)):
        ws.row_dimensions[r].height = 45


def main():
    sc = [r for r in csv.DictReader(open(os.path.join(DB, "5_ShortCircuit_DG_out.csv")))
          if r["Fault type"] == "LG" and float(r["Zf (ohm)"]) == 3.0]
    wb = Workbook()

    # ---- 1 method ---------------------------------------------------------------------------
    ws = wb.active
    ws.title = "Method"
    lines = [
        ["Minimum fault current If,min of the recloser zones (DG out of service)"],
        [""],
        ["Software", "DIgSILENT PowerFactory 2021, IEEE 13-node feeder model (project IEEE13 DSDR Fuse Coordination)"],
        ["Calculation", "Short circuit, complete method (pre-fault load flow included), initial symmetrical current Ikss"],
        ["Fault", "Line-to-ground (LG) through a fault resistance Rf = 3 ohm"],
        ["Locations", "Every node of the zone and every phase present at that node"],
        ["DG", "Out of service (the pickup is designed without DG)"],
        ["Current read", "Current through the recloser = largest of its three phase currents (fault current + load "
                         "current, added as phasors, because the complete method keeps the load flowing)"],
        ["R1 zone", ", ".join(ZONES["R1"])],
        ["R2 zone", ", ".join(ZONES["R2"]) + "  (downstream of R2)"],
        ["If,min", "Lowest recloser current over all LG 3-ohm faults of the zone  ->  =MIN(IF(...)) in sheet If_min_R1_R2"],
        ["Pickup check", "The pickup must be below If,min, so that the recloser still detects the weakest fault of its zone"],
        [""],
        ["Why If,min is not at the farthest node",
         "The farthest node (652) gives the smallest current AT THE FAULT, but the recloser also carries the load "
         "current of its phase. The smallest RECLOSER current is therefore at 680 on phase B, the phase with the "
         "smallest sum of load and fault current."],
    ]
    for i, row in enumerate(lines, 1):
        for j, v in enumerate(row, 1):
            c = ws.cell(row=i, column=j, value=v)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            if j == 1:
                c.font = HEAD
    ws["A1"].font = Font(bold=True, size=14)
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 110

    # ---- 2 all LG 3-ohm faults --------------------------------------------------------------
    ws = wb.create_sheet("LG_3ohm_faults")
    rows = [["Faulted node", "Faulted phase", "Rf (ohm)", "Current at the fault (A)", "Current through R1 (A)",
             "Current through R2 (A)", "In R1 zone", "In R2 zone"]]
    for r in sc:
        n = r["Faulted bus"]
        rows.append([n, r["Phases"], 3, float(r["Fault current (A)"]), float(r["R1 current (A)"]),
                     float(r["R2 current (A)"]), "yes" if n in ZONES["R1"] else "no", "yes" if n in ZONES["R2"] else "no"])
    grid(ws, 1, rows, [13, 13, 9, 22, 22, 22, 11, 11])
    last = len(rows)
    for i in range(2, last + 1):
        for col in (4, 5, 6):
            ws.cell(row=i, column=col).number_format = "0.0"
    ws.freeze_panes = "A2"
    # highlight the two minima
    for i in range(2, last + 1):
        if ws.cell(row=i, column=1).value == "680" and ws.cell(row=i, column=2).value == "B":
            for col in (5, 6):
                ws.cell(row=i, column=col).fill = KEY
    ws.cell(row=last + 2, column=1, value="Yellow: the lowest recloser current of each zone (If,min).").font = Font(italic=True)
    ws.cell(row=last + 3, column=1, value="Node 634 is behind the 4.16/0.48 kV transformer: in no recloser zone "
                                          "for this check (its own section is XFM-1).").font = Font(italic=True)

    # ---- 3 If,min: values, and the Excel formula that reproduces each -----------------------
    # (values are written, not only formulas, so the sheet reads correctly even where Excel cannot recalculate)
    ws = wb.create_sheet("If_min_R1_R2")
    D = "LG_3ohm_faults!"
    rng = lambda col: "%s$%s$2:$%s$%d" % (D, col, col, last)
    head = ["Recloser", "Zone (nodes)", "Farthest node", "Current at the fault, farthest node (A)",
            "Recloser current, farthest node (A)", "If,min = lowest recloser current in the zone (A)",
            "Node of If,min", "Phase of If,min", "Inom (A)", "Ip = 1.25 x Inom (A)", "Pickup applied (A)",
            "Setting", "Check: pickup < If,min"]
    grid(ws, 1, [head], [10, 34, 10, 18, 18, 22, 11, 11, 10, 13, 13, 30, 18])
    formulas = [["Column", "Excel formula (R1 row; R2 uses column F / H instead of E / G)"]]
    for k, (dev, key, zone_col, col, zcol) in enumerate((("R1", "Current through R1 (A)", "R1", "E", "G"),
                                                         ("R2", "Current through R2 (A)", "R2", "F", "H"))):
        r = k + 2
        far = FARTHEST[dev]
        setting, ip_applied, inom = PICKUP[dev]
        recs = [x for x in rows[1:] if x[0] in ZONES[dev]]
        cur = 4 if dev == "R1" else 5
        at_far = [x for x in recs if x[0] == far]
        low = min(recs, key=lambda x: x[cur])
        vals = [dev, ", ".join(ZONES[dev]), far, min(x[3] for x in at_far), min(x[cur] for x in at_far), low[cur],
                low[0], low[1], inom, round(1.25 * inom, 1), ip_applied, setting,
                "OK: %.0f < %.1f" % (ip_applied, low[cur]) if ip_applied < low[cur] else "NOT OK"]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.border = BOX
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            if c in (4, 5, 6, 10):
                cell.number_format = "0.0"
        ws.cell(row=r, column=6).fill = KEY
        if dev == "R1":
            formulas += [
                ["D  current at the fault, farthest node", "=MIN(IF(%s=C2,%s))   (array formula: Ctrl+Shift+Enter)" % (rng("A"), rng("D"))],
                ["E  recloser current, farthest node", "=MIN(IF(%s=C2,%s))   (array)" % (rng("A"), rng(col))],
                ["F  If,min", "=MIN(IF(%s=\"yes\",%s))   (array)" % (rng(zcol), rng(col))],
                ["G  node of If,min", "=INDEX(%s,MATCH(1,(%s=F2)*(%s=\"yes\"),0))   (array)" % (rng("A"), rng(col), rng(zcol))],
                ["H  phase of If,min", "=INDEX(%s,MATCH(1,(%s=F2)*(%s=\"yes\"),0))   (array)" % (rng("B"), rng(col), rng(zcol))],
                ["J  pickup by eq. (3)", "=1.25*I2"],
                ["M  check", "=IF(K2<F2,\"OK\",\"NOT OK\")"]]
    ws.cell(row=5, column=1, value="How each value is obtained (sheet LG_3ohm_faults holds the data):").font = HEAD
    grid(ws, 6, formulas)
    ws.cell(row=6 + len(formulas) + 1, column=1,
            value="Values from the PowerFactory database: R1 If,min 1074.4 A and R2 If,min 878.5 A, both for the LG "
                  "fault through 3 ohm at 680, phase B.").font = Font(italic=True)

    # ---- 4 all sections ---------------------------------------------------------------------
    ws = wb.create_sheet("All_sections")
    src = list(csv.reader(open(os.path.join(DB, "Ifmin_DG_out.csv"))))
    src[0] = ["Protection section", "Farthest node", "Line length to it (ft)", "Fault type", "Faulted phase",
              "Rf (ohm)", "Current at the fault (A)", "Section current, fault at the farthest node (A)",
              "Lowest LG 3-ohm section current (If,min)"]
    grid(ws, 1, src, [16, 10, 12, 8, 9, 8, 14, 20, 34])
    ws.freeze_panes = "A2"

    farthest(wb, sc)
    hand_check(wb)
    try:
        wb.save(OUT)
        out = OUT
    except PermissionError:
        out = OUT.replace(".xlsx", "_new.xlsx")
        wb.save(out)
    print("EXCEL:", out)
    return out


if __name__ == "__main__":
    main()
