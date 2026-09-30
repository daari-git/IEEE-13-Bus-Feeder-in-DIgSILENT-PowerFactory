"""
Configure recloser relays R1 and R2 of the IEEE 13-node feeder as in Yousaf et al. (2022).

  R1: RG60 end of line RG60-632,  Ip = 1.25 x 587.6 = 734.5 A,  TDS 0.5 / 10
  R2: 671 end of line 632-671,    Ip = 1.25 x 479.0 = 598.8 A,  TDS 0.8 / 4.0
  Relay: GE IAC77B801A (60 Hz), IAC extremely inverse. R2's TDS are not given in the paper;
  0.8 / 4.0 fit its Table III.

The IAC77 has one phase time-overcurrent stage, so each recloser is two relays of this type
in the same cubicle, sharing one CT:  "R1" = fast curve,  "R1 Delayed" = delayed curve.
The earth and instantaneous stages are switched out of service (the paper uses phase
curves only).

The relay's current setting is a drop-down of taps (0.5 .. 4 A secondary) that scripts
cannot change, so the CT ratio is chosen to bring a tap close to Ip:
  R1: CT 900/5,  tap 4.0 A -> 720 A  (-2.0 %)      R2: CT 1000/5, tap 3.0 A -> 600 A (+0.2 %)
The script sets the CTs, curves and time dials, and checks the taps set by hand in each
Toc element. It then runs a load flow and a 3-phase fault below each recloser and compares
the trip times with the GE IAC curve. Everything is printed in the Output Window and saved
as Recloser_config.txt.
"""

import os

import powerfactory as pf

OUT_DIR = r"D:\Protection and co-ordination\Result\Logs"
OUT_TXT = os.path.join(OUT_DIR, "Recloser_config.txt")
OUT_PF = os.path.join(OUT_DIR, "PF_output_window.txt")
os.makedirs(OUT_DIR, exist_ok=True)

RECLOSERS = {
    "R1": dict(term="RG60", fault="632", ip=734.5, tds_f=0.5, tds_d=10.0, ct=900, tap=4.0),
    "R2": dict(term="671", fault="671", ip=598.8, tds_f=0.8, tds_d=4.0, ct=1000, tap=3.0),
}
DELAYED_SUFFIX = " Delayed"
CT_SECONDARY = 5.0

RELAY_TYPE = ""
RELAY_TYPE_PATTERNS = ["IAC77B801A*", "IAC77B*", "IAC77*", "*IAC*"]
PREFER_PATH = "60Hz"                 # IEEE 13-node feeder is a 60 Hz system
CHAR_PATTERNS = ["*IAC*Extrem*", "*Extrem*"]

# Delete relays that have no relay type and are not R1/R2 (they block the load flow)
DELETE_EXTRAS = True

IAC_EI = (0.0040, 0.6379, 0.6200, 1.7872, 0.2461)   # GE IAC extremely inverse, TDS = 1
CUBICLE_KEYS = ("bus1", "bus2", "bushv", "buslv")
PHASES = ("A", "B", "C")
EARTH_HINTS = ("earth", "ground", "gnd", "3i0", "neutral", "ie>", "in>", "i0", "sef")
TRIP_VARS = ["c:ttrip", "c:yt", "c:Tdelay", "c:tact"]

app = pf.GetApplication()
lines = []


def out(s=""):
    lines.append(s)
    app.PrintPlain(s)


def attr(obj, name, default=None):
    try:
        v = obj.GetAttribute(name)
        return default if v is None else v
    except Exception:
        return default


def setattr_ok(obj, name, value):
    try:
        obj.SetAttribute(name, value)
        return True
    except Exception as e:
        out("    could not set %s.%s = %s (%s)" % (obj.loc_name, name, value, e))
        return False


def iac_ei(m):
    a, b, c, d, e = IAC_EI
    x = m - c
    return a + b / x + d / x ** 2 + e / x ** 3 if m > 1.0 else float("nan")


# ---- libraries -----------------------------------------------------------------------------
def library_folders():
    folders = []
    for get in (lambda: app.GetProjectFolder("equip"), lambda: app.GetGlobalLibrary()):
        try:
            f = get()
            if f is not None:
                folders.append(f)
        except Exception:
            pass
    if len(folders) < 2:
        try:
            root = app.GetCurrentUser().GetParent()
            folders += [f for f in root.GetContents("Library*") if f is not None]
        except Exception:
            pass
    return folders


def find_relay_type():
    folders = library_folders()
    for p in ([RELAY_TYPE] if RELAY_TYPE else RELAY_TYPE_PATTERNS):
        hits = []
        for f in folders:
            hits += f.GetContents("%s.TypRelay" % p, 1)
        if hits:
            preferred = [h for h in hits if PREFER_PATH in h.GetFullName()]
            return (preferred or hits)[0]
    return None


def find_characteristic(toc):
    """IAC extremely inverse curve that belongs to this element's own type."""
    places = [attr(toc, "typ_id")]
    rtype = attr(toc.GetParent(), "typ_id")
    places.append(rtype)
    if rtype is not None:
        places.append(rtype.GetParent())
    for place in places:
        if place is None:
            continue
        for p in CHAR_PATTERNS:
            hits = place.GetContents("%s.TypChatoc" % p, 1)
            if hits:
                return hits[0]
    return None


# ---- network -------------------------------------------------------------------------------
def term_of(relay):
    t = attr(relay.GetParent(), "cterm")
    return t.loc_name if t is not None else None


def relay_at(name, term):
    for r in app.GetCalcRelevantObjects("*.ElmRelay"):
        if r.loc_name == name and term_of(r) == term:
            return r
    return None


def cubicle_branch(cub):
    br = attr(cub, "obj_id")
    for k in CUBICLE_KEYS:
        if br is not None and attr(br, k) == cub:
            return br, k
    return br, None


def close_breaker(cub):
    for sw in cub.GetContents("*.StaSwitch"):
        if attr(sw, "on_off") == 0:
            sw.on_off = 1
            out("  breaker %s in %s was OPEN - closed" % (sw.loc_name, cub.loc_name))


def ensure_ct(cub, name, prim, sec):
    cts = cub.GetContents("*.StaCt")
    ct = cts[0] if cts else cub.CreateObject("StaCt", name + " CT")
    equip = app.GetProjectFolder("equip")
    tname = "CT %.0f-%.0f" % (prim, sec)
    found = equip.GetContents(tname + ".TypCt")
    typ = found[0] if found else equip.CreateObject("TypCt", tname)
    for a, v in (("primtaps", [prim]), ("sectaps", [sec]), ("Iprim", prim), ("Isec", sec)):
        try:
            typ.SetAttribute(a, v)
        except Exception:
            pass
    ct.typ_id = typ
    setattr_ok(ct, "ptapset", prim)
    setattr_ok(ct, "stapset", sec)
    out("  CT %s: %s / %s A" % (ct.loc_name, attr(ct, "ptapset"), attr(ct, "stapset")))


# ---- relay settings ------------------------------------------------------------------------
def is_earth(e):
    t = attr(e, "typ_id")
    label = (e.loc_name + " " + (t.loc_name if t else "")).lower()
    return any(h in label for h in EARTH_HINTS)


def prepare(relay, rtype):
    """Assign the type, switch off unused stages, set the curve. Returns the phase stage."""
    if attr(relay, "typ_id") != rtype:
        relay.typ_id = rtype
    try:
        relay.SlotUpdate()
    except Exception as e:
        out("  SlotUpdate failed: %s" % e)
    tocs = relay.GetContents("*.RelToc", 1)
    phase = [e for e in tocs if not is_earth(e)]
    for e in tocs:
        if is_earth(e) or e not in phase[:1]:
            setattr_ok(e, "outserv", 1)
    for e in relay.GetContents("*.RelIoc", 1):
        setattr_ok(e, "outserv", 1)
    if not phase:
        out("  %s: no phase time-overcurrent stage in this relay type" % relay.loc_name)
        return None
    toc = phase[0]
    setattr_ok(toc, "outserv", 0)
    charac = find_characteristic(toc)
    if charac is not None and attr(toc, "pcharac") != charac:   # re-setting may reset the tap
        setattr_ok(toc, "pcharac", charac)
    return toc


def finish(relay, toc, cfg, ratio, tds, label):
    """Set curve time dial; the tap (Ipset) is a drop-down that scripts cannot change, so it
    is only checked against the tap wanted in RECLOSERS."""
    setattr_ok(toc, "Tpset", tds)
    c = attr(toc, "pcharac")
    tap = attr(toc, "Ipset", 0.0)
    ok = abs(tap - cfg["tap"]) < 1e-6
    out("  %-12s (%s) curve %s, time dial %s, tap %s A = %.1f A primary  %s" % (
        relay.loc_name, label, c.loc_name if c else "NONE", attr(toc, "Tpset"), tap,
        tap * ratio, "OK" if ok else "<-- set Current Setting to %.1f by hand" % cfg["tap"]))
    return ok


def configure(name, cfg, rtype):
    out("=" * 78)
    relay = relay_at(name, cfg["term"])
    if relay is None:
        out("%s: no relay named %s at terminal %s - add it there first" % (name, name, cfg["term"]))
        return None
    cub = relay.GetParent()
    br, key = cubicle_branch(cub)
    out("%s: %s, cubicle %s, branch %s (%s)" % (
        name, cfg["term"], cub.loc_name, br.loc_name if br else "?", key))
    close_breaker(cub)

    dname = name + DELAYED_SUFFIX
    found = cub.GetContents(dname + ".ElmRelay")
    delayed = found[0] if found else cub.CreateObject("ElmRelay", dname)
    if not found:
        out("  created relay %s in %s" % (dname, cub.loc_name))

    toc_f, toc_d = prepare(relay, rtype), prepare(delayed, rtype)
    if toc_f is None or toc_d is None:
        return None
    prim = float(cfg["ct"])
    ratio = prim / CT_SECONDARY
    out("  CT %.0f/%.0f, tap %.1f A -> %.1f A primary (Ip %.1f A, %+.1f %%)" % (
        prim, CT_SECONDARY, cfg["tap"], cfg["tap"] * ratio, cfg["ip"],
        100.0 * (cfg["tap"] * ratio / cfg["ip"] - 1)))
    ensure_ct(cub, name, prim, CT_SECONDARY)
    try:                                   # let both relays pick up the (re-typed) CT
        relay.SlotUpdate()
        delayed.SlotUpdate()
    except Exception:
        pass
    ok = finish(relay, toc_f, cfg, ratio, cfg["tds_f"], "fast")
    ok = finish(delayed, toc_d, cfg, ratio, cfg["tds_d"], "delayed") and ok
    if not ok:
        return None
    return [relay, delayed], br, key, cfg["tap"] * ratio


def trip_check(name, cfg, relays, br, key, ip_set):
    out("-" * 78)
    ldf = app.GetFromStudyCase("ComLdf")
    ldf.iopt_net = 1
    if ldf.Execute() != 0:
        out("  load flow failed - trip check skipped")
        return
    terms = {t.loc_name: t for t in app.GetCalcRelevantObjects("*.ElmTerm")}
    shc = app.GetFromStudyCase("ComShc")
    shc.iopt_mde = 3
    shc.iopt_allbus = 0
    shc.shcobj = terms[cfg["fault"]]
    shc.iopt_shc = "3rst"
    shc.Rf = 0.0
    shc.Xf = 0.0
    try:
        shc.SetAttribute("iopt_prot", 1)    # evaluate protection devices, if available
    except Exception:
        pass
    if shc.Execute() != 0:
        out("  short circuit at %s failed" % cfg["fault"])
        return
    i_a = 1000.0 * max(abs(attr(br, "m:Ikss:%s:%s" % (key, p), 0.0)) for p in PHASES)
    m = i_a / ip_set
    out("%s: 3-phase fault at %s, %.0f A through the recloser, M = %.2f (pickup %.1f A)" % (
        name, cfg["fault"], i_a, m, ip_set))
    out("  GE IAC curve: fast %.3f s, delayed %.3f s" % (
        cfg["tds_f"] * iac_ei(m), cfg["tds_d"] * iac_ei(m)))
    for r in relays:
        for obj in [r] + list(r.GetContents("*.RelToc", 1)):
            res = ["%s=%s" % (v, attr(obj, v)) for v in TRIP_VARS if attr(obj, v) is not None]
            if res:
                out("  %-12s %-10s %s" % (r.loc_name, obj.loc_name, "  ".join(res)))


def delete_extras():
    keep = set()
    for name, cfg in RECLOSERS.items():
        keep.add((name, cfg["term"]))
        keep.add((name + DELAYED_SUFFIX, cfg["term"]))
    for r in app.GetCalcRelevantObjects("*.ElmRelay"):
        where = term_of(r)
        if (r.loc_name, where) in keep:
            continue
        msg = "Extra relay %s at %s" % (r.loc_name, where)
        if attr(r, "typ_id") is not None:
            out(msg + " has a relay type - left in place")
        elif DELETE_EXTRAS:
            r.Delete()
            out(msg + " (no type) - deleted")
        else:
            out(msg + " (no type) - blocks the load flow; delete it or set DELETE_EXTRAS")


def main():
    try:
        app.GetOutputWindow().Clear()
    except Exception:
        pass

    delete_extras()
    rtype = find_relay_type()
    out("Relay type: %s" % (rtype.GetFullName() if rtype else "NONE"))
    if rtype is not None:
        dgs = app.GetCalcRelevantObjects("*.ElmSym")
        dg_state = [g.outserv for g in dgs]
        try:
            for g in dgs:
                g.outserv = 1
            done = []
            for name, cfg in RECLOSERS.items():
                res = configure(name, cfg, rtype)
                if res:
                    done.append((name, cfg, res))
            for name, cfg, res in done:
                try:
                    trip_check(name, cfg, *res)
                except Exception as e:
                    out("  trip check failed: %s" % e)
        finally:
            for g, s in zip(dgs, dg_state):
                g.outserv = s
    out("=" * 78)
    for sw in (app.GetCalcRelevantObjects("*.StaSwitch") +
               app.GetCalcRelevantObjects("*.ElmCoup")):
        if attr(sw, "on_off") == 0:
            out("Open switch: %s" % sw.GetFullName())

    with open(OUT_TXT, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    app.PrintPlain("Saved: " + OUT_TXT)
    try:
        app.GetOutputWindow().Save(OUT_PF)
    except Exception:
        pass


main()
