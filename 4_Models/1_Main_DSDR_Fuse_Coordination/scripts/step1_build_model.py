"""
Step 1 - build the protection system of Fig. 6 in a clean copy of the IEEE 13-node feeder.

  * removes every relay, fuse and CT left in the project (fresh start)
  * adds the lateral nDL - DL for the distributed-load fuse F-DL (fault location "DL")
  * sets the synchronous DG to the data of Table I
  * places the 15 fuses (Gould-Shawmut A055C / gL, see protection_data.FUSES)
  * places R1 (2 x GE IAC77B801A: fast, delayed) and R2 (4 x GE/Alstom CDG34: forward fast,
    forward delayed, reverse fast, reverse delayed) with their CTs.
Settings are written afterwards by step4_apply_settings.py from results/settings.json.
"""

from pf_setup import activate, attr, out, obj, lib_type, save_table1
from protection_data import FUSES, RECLOSERS, R2_UNITS, DL_LUMP

app = activate(build=True)
grid = obj("632", "ElmTerm").GetParent()


def cubicle(loc):
    if loc[0] == "load":
        return obj(loc[1], "ElmLod").GetAttribute("bus1")
    for cls in ("ElmLne", "ElmTr2", "ElmCoup"):
        hits = app.GetCalcRelevantObjects("%s.%s" % (loc[1], cls))
        if hits:
            return hits[0].GetAttribute(loc[2])
    raise KeyError(loc)


# ---- 1. fresh start --------------------------------------------------------------------------
n = 0
for cls in ("ElmRelay", "RelFuse", "StaCt"):
    for o in grid.GetContents("*." + cls, 1):
        o.Delete()
        n += 1
for f in app.GetProjectFolder("equip").GetContents("Fuse Types Yousaf 2022*"):
    f.Delete()
out("Removed %d old protection objects" % n)

# ---- 2. distributed-load lateral nDL - DL ------------------------------------------------------
if not app.GetCalcRelevantObjects("DL.ElmTerm"):
    ndl = obj("nDL", "ElmTerm")
    dl = grid.AddCopy(ndl, "DL")
    for c in dl.GetContents("*.StaCubic"):
        c.Delete()
    proto = obj("LOHL632-671start", "ElmLne")
    line = grid.AddCopy(proto, "LDL")
    line.SetAttribute("bus1", ndl.CreateObject("StaCubic", "Cub_LDL"))
    line.SetAttribute("bus2", dl.CreateObject("StaCubic", "Cub_LDL"))
    line.SetAttribute("dline", 10.0)                  # 10 ft (project length unit)
    load = obj(DL_LUMP, "ElmLod")
    old = load.GetAttribute("bus1")
    load.SetAttribute("bus1", dl.CreateObject("StaCubic", "Cub_Load"))
    old.Delete()
    out("Added terminal DL and 10 ft lateral LDL (config 601); %s moved to DL" % DL_LUMP)

# ---- 3. DG of Table I --------------------------------------------------------------------------
sym = obj("Synchronous Machine", "ElmSym")
typ = sym.typ_id
table1 = dict(xl=0.05, rstr=0.0014, xd=1.4, xq=1.372, xds=0.231, xqs=0.8, xdss=0.118, xqss=0.118,
              tds0=5.5, tdss0=0.05, tqs0=1.25, tqss0=0.19, h=0.75)
# The machine type takes short-circuit time constants; convert Table I's open-circuit ones.
sc_tc = dict(tds=5.5 * 0.231 / 1.4, tdss=0.05 * 0.118 / 0.231, tqs=1.25 * 0.8 / 1.372,
             tqss=0.19 * 0.118 / 0.8)
# Table I gives X'q and T'q0, i.e. a round-rotor machine; with the salient-pole model PowerFactory
# ignores them and reads T''q as T''q0 * X''q / Xq, which turns T''q0 = 0.19 s into 0.326 s.
for k, v in [("iturbo", 1)] + list(table1.items()) + list(sc_tc.items()):
    try:
        typ.SetAttribute(k, v)
    except Exception:
        pass
out("DG (%s): %s" % (typ.loc_name, ", ".join("%s=%s" % (k, round(attr(typ, k, float("nan")), 4))
                                              for k in table1)))
save_table1()

# ---- 4. fuses ---------------------------------------------------------------------------------
for name, (loc, tname, src) in FUSES.items():
    cub = cubicle(loc)
    f = cub.CreateObject("RelFuse", name)
    f.typ_id = lib_type(tname + ".TypFuse", "ProtFuse")
    out("  %-7s %-10s at %-6s (%s)" % (name, tname, cub.GetAttribute("cterm").loc_name, src))


# ---- 5. reclosers -----------------------------------------------------------------------------
def ct_type(prim):
    equip = app.GetProjectFolder("equip")
    name = "CT %.0f-5A" % prim
    hit = equip.GetContents(name + ".TypCt")
    t = hit[0] if hit else equip.CreateObject("TypCt", name)
    t.SetAttribute("primtaps", [prim])
    t.SetAttribute("sectaps", [5.0])
    return t


def add_relay(cub, name, rtype):
    r = cub.CreateObject("ElmRelay", name)
    r.typ_id = rtype
    r.SlotUpdate()
    for e in r.GetContents("*.RelIoc") + r.GetContents("*Earth*.RelToc"):
        e.SetAttribute("outserv", 1)                   # phase time-overcurrent only
    return r


iac = lib_type("IAC77B801A.TypRelay", "ProtRelay\\GE\\IAC\\60Hz")
cdg = lib_type("CDG34-5A (1-4).TypRelay", "CDG34 A & B & C\\Prefered Taps")
for rname, cfg in RECLOSERS.items():
    cub = cubicle(cfg["loc"])
    ct = cub.CreateObject("StaCt", "CT " + rname)
    ct.typ_id = ct_type(cfg["ct"])
    ct.SetAttribute("ptapset", cfg["ct"])
    ct.SetAttribute("stapset", 5.0)
    units = ["R1 Fast", "R1 Delayed"] if rname == "R1" else R2_UNITS
    for u in units:
        add_relay(cub, u, iac if rname == "R1" else cdg)
    out("  %s: %s at %s, CT %.0f/5, units %s" % (rname, cfg["relay"], cub.GetAttribute("cterm").loc_name,
                                                cfg["ct"], ", ".join(units)))

ldf = app.GetFromStudyCase("ComLdf")
out("Load flow after build: %s" % ("OK" if ldf.Execute() == 0 else "FAILED"))
