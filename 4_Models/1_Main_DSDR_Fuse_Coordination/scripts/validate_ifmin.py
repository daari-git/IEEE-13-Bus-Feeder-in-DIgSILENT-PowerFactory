"""
Data for a hand check of the minimum fault current (LG through 3 ohm at 680, phase B, DG out):
  - pre-fault (load-flow) phase currents at R1 and R2 and the pre-fault voltage at 680
  - the fault current at 680 and the phase currents through R1 and R2 during the fault
  - the Thevenin sequence impedances at 680 (as far as PowerFactory reports them)
Nothing in the model is changed (the DG is switched back as it was).
Output: results/database/Ifmin_validation.json
"""

import cmath
import json
import math
import os

import database_study as ds
from pf_setup import attr, clean_variation

NODE, RF = "680", 3.0


def pol(z):
    return [round(abs(z), 3), round(math.degrees(cmath.phase(z)), 2)]


def main():
    sym = ds.sym
    state = sym.GetAttribute("outserv")
    out = {}
    try:
        sym.SetAttribute("outserv", 1)                                     # DG out
        if ds.ldf.Execute() != 0:
            raise RuntimeError("load flow failed")
        t = ds.TERMS[NODE]
        out["V_pre_680"] = {p: [attr(t, "m:U:" + p), attr(t, "m:phiu:" + p), attr(t, "m:u:" + p)] for p in "ABC"
                            if (attr(t, "m:u:" + p, 0.0) or 0.0) > 0.01}
        v1pre = {n: ds.v1_at(d["term"]) for n, d in ds.DEV.items()}
        for name, d in ds.DEV.items():
            ph = [d["fwd"] * x for x in ds.phasors(d["el"], d["side"], "m:I", 1000.0)]
            out["I_load_" + name] = {p: pol(x) for p, x in zip("ABC", ph)}
        rec = None
        for idx in (0, 1, 2):
            r = ds.run_fault(NODE, "LG", idx, RF, v1pre)
            if r and r["phases"] == "B":
                rec = r
                break
        if rec is None:
            raise RuntimeError("phase-B fault at 680 not found")
        out["I_fault_680"] = {p: round(i, 2) for p, i in zip("ABC", rec["ifault"])}
        ang = {}
        for var in ("m:phiikss:B", "m:phii:B", "m:phi_ikss:B"):
            v = attr(t, var)
            if v is not None:
                ang[var] = v
        out["I_fault_680_angle_candidates"] = ang
        for name, d in ds.DEV.items():
            ph = [d["fwd"] * x for x in ds.phasors(d["el"], d["side"], "m:Ikss", 1000.0)]
            out["I_fault_" + name] = {p: pol(x) for p, x in zip("ABC", ph)}
        z = {}
        for var in ("m:R0", "m:X0", "m:R1", "m:X1", "m:R2", "m:X2", "m:Z0", "m:Z1", "m:Z2", "m:Rk", "m:Xk",
                    "m:Zk", "m:Skss", "m:Ikss", "m:ikss", "m:R0toR1", "m:X0toX1", "m:R1k", "m:X1k", "m:R0k", "m:X0k"):
            v = attr(t, var)
            if v is not None:
                z[var] = v
        out["Z_at_680_candidates"] = z
    finally:
        sym.SetAttribute("outserv", state)
        clean_variation()
    path = os.path.join(ds.OUT, "Ifmin_validation.json")
    json.dump(out, open(path, "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
