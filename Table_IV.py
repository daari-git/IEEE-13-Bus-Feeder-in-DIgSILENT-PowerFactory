"""
Table IV of Yousaf et al. (2022) in the PowerFactory Output Window: operating times of R1,
R2 and the primary fuse for a fault at each node, model and paper.

For each node the largest bolted fault that exists there (3-phase, else LLG, LL, LG) is
calculated with the DG in service (Complete method). Times use the model's curves (the
fault and curve code of Fig14_Coordination.py):
  R1        GE IAC extremely inverse, Ip 720 A, TDS 0.5 / 10
  R2        forward: Ip 600 A, TDS 0.8 / 4.0; upstream of R2 the DSDR reverse setting
  fuse      primary fuse of the faulted path, melting time eq. (6) with Table III b_i
Same rules as make_figures.py (Result\\Table_IV_model.csv).

Run: Python Script (ComPython) in the study case -> Execute.
"""

import os
import runpy

DIR = r"D:\Protection and co-ordination"

try:
    app            # one shared Application when loaded by Show_Progress.py
except NameError:
    import powerfactory as pf
    app = pf.GetApplication()
C = runpy.run_path(os.path.join(DIR, "Fig14_Coordination.py"), run_name="table4",
                   init_globals={"app": app})
out = C["out"]

NODES = ["632", "633", "645", "646", "nDL", "671", "692", "675", "684", "680", "611", "652"]
# paper: R1 fast, R1 delayed, R2 fast, R2 delayed, fuse t_MMT
PAPER = {"632": (0.070, 1.398, 0.045, 0.514, None), "633": (0.094, 1.880, 0.052, 0.706, 0.163),
         "645": (0.105, 2.095, 0.087, 1.659, 0.276), "646": (0.128, 2.555, 0.103, 2.046, 0.181),
         "nDL": (0.087, 1.733, 0.076, 1.402, 0.248), "671": (0.105, 2.091, 0.068, 1.113, None),
         "692": (0.115, 2.307, 0.072, 1.258, 0.175), "675": (0.121, 2.414, 0.074, 1.332, 0.185),
         "684": (0.125, 2.507, 0.075, 1.394, 0.205), "680": (0.137, 2.747, 0.079, 1.555, None),
         "611": (0.326, 6.523, 0.146, 4.385, 0.417), "652": (0.676, 13.525, 0.143, 9.370, 0.233)}


def row_times(node, res):
    """(fault currents and times) for one node: R1 F/D, R2 F/D, fuse, fuse MMT."""
    r2 = C["R2_RV"] if node in C["UPSTREAM_OF_R2"] else C["R2"]
    r1f, r1d = C["rec_times"](C["R1"], res["R1"])
    r2f, r2d = C["rec_times"](r2, res["R2"])
    f = C["PRIMARY_FUSE"].get(node)
    melt = None
    if f:
        i_f = res["R1"] + res["R2"] if f == "F-DL" else res.get(f, 0.0)
        melt = C["mmt"](f, i_f)
    return r1f, r1d, r2f, r2d, f, melt


def fmt(v, w=8):
    if v is None:
        return "---".rjust(w)
    return ("%.3f" % v).rjust(w) if v < 1000 else "no trip".rjust(w)


def print_table(heading, rows, with_fault):
    line = "-" * (74 if with_fault else 60)
    out("")
    out("   " + heading)
    out("   " + line)
    out("   %-8s %s| %-17s | %-17s | %8s" % ("Faulted", "Fault   " if with_fault else "",
                                            "        R1", "        R2", "Fuse"))
    out("   %-8s %s| %8s %8s | %8s %8s | %8s%s" % (
        "Node", "type    " if with_fault else "", "Fast", "Delayed", "Fast", "Delayed",
        "(t_MMT)", "   fuse" if with_fault else ""))
    out("   " + line)
    for r in rows:
        out("   %-8s %s| %s %s | %s %s | %s%s" % (
            C["LABEL"].get(r["node"], r["node"]),
            ("%-8s" % r["fault"]) if with_fault else "",
            fmt(r["t"][0]), fmt(r["t"][1]), fmt(r["t"][2]), fmt(r["t"][3]), fmt(r["t"][4]),
            ("   " + (r["fuse"] or "---")) if with_fault else ""))
    out("   " + line)


def main(clear=True):
    if clear:
        try:
            app.GetOutputWindow().Clear()
        except Exception:
            pass
    shc = app.GetFromStudyCase("ComShc")
    terms = {t.loc_name: t for t in app.GetCalcRelevantObjects("*.ElmTerm")}
    pts = C["points"]()
    dgs = app.GetCalcRelevantObjects("*.ElmSym")
    state = [g.outserv for g in dgs]
    model = []
    app.EchoOff()
    try:
        for g in dgs:
            g.outserv = 0
        for node in NODES:
            for ft in reversed(C["FAULTS"]):              # LLL, LLG, LL, LG
                res = C["fault"](terms[node], ft, pts, shc)
                if res is not None and res.get("R1"):
                    r1f, r1d, r2f, r2d, f, melt = row_times(node, res)
                    model.append(dict(node=node, fault=ft, fuse=f,
                                      t=(r1f, r1d, r2f, r2d, melt)))
                    break
    finally:
        app.EchoOn()
        for g, st in zip(dgs, state):
            g.outserv = st

    out("TABLE IV")
    out("VALIDATION OF RECLOSER-FUSE COORDINATION FOR DIFFERENT FAULTS")
    print_table("MODEL (PowerFactory, DG in service, bolted fault; R2 as DSDR upstream of R2)",
                model, True)
    print_table("PAPER (Yousaf et al. 2022)",
                [dict(node=n, t=PAPER[n]) for n in NODES], False)
    out("")
    out("   Model / paper, R1 fast:  " + "  ".join(
        "%s %.2f" % (C["LABEL"].get(r["node"], r["node"]), r["t"][0] / PAPER[r["node"]][0])
        for r in model))
    out("   R1 agrees with the paper; R2 and the fuses differ because the fuses follow eq. (6)")
    out("   with the Table III b_i, and the paper's R2 settings are not published.")


if __name__ == "__main__":
    main()
