"""
Draw the time-overcurrent curves of reclosers R1 and R2 (fast and delayed) in one plot.

The plot is built through the scripting API (SetVipage + VisOcplot), so PowerFactory's
"insert plot" dialog, which crashes PowerFactory 2021 SP2, is never opened. The page is
called "Recloser TCC" and is rebuilt on every run.

Before plotting, each relay's time-overcurrent stages are listed. A relay that is out of
service, or whose phase stage is out of service or has no curve, draws nothing.
"""

import powerfactory as pf

PAGE = "Recloser TCC"
PLOT = "R1 R2"
# relay name, terminal, colour, line style, width (colour: 2 red, 4 blue; style: 1 solid, 2 dashed)
RELAYS = [
    ("R1", "RG60", 2, 1, 2),
    ("R1 Delayed", "RG60", 2, 2, 2),
    ("R2", "671", 4, 1, 2),
    ("R2 Delayed", "671", 4, 2, 2),
]

app = pf.GetApplication()


def out(s=""):
    app.PrintPlain(s)


def attr(obj, name, default=None):
    try:
        v = obj.GetAttribute(name)
        return default if v is None else v
    except Exception:
        return default


def term_of(relay):
    t = attr(relay.GetParent(), "cterm")
    return t.loc_name if t is not None else None


def relay_at(name, term):
    for r in app.GetCalcRelevantObjects("*.ElmRelay"):
        if r.loc_name == name and term_of(r) == term:
            return r
    return None


def report(relay):
    """Print what the plot needs from this relay; True if at least one stage can draw."""
    typ = attr(relay, "typ_id")
    out("%-12s at %s: type %s, out of service %s" % (
        relay.loc_name, term_of(relay), typ.loc_name if typ else "NONE", attr(relay, "outserv")))
    drawable = False
    for toc in relay.GetContents("*.RelToc", 1):
        c = attr(toc, "pcharac")
        on = attr(toc, "outserv", 0) == 0
        out("    %-20s in service %-3s curve %s, tap %s A, time dial %s" % (
            toc.loc_name, "yes" if on else "no", c.loc_name if c else "NONE",
            attr(toc, "Ipset"), attr(toc, "Tpset")))
        drawable = drawable or (on and c is not None)
    for ct in relay.GetParent().GetContents("*.StaCt"):
        out("    CT %s: %s / %s A" % (ct.loc_name, attr(ct, "ptapset"), attr(ct, "stapset")))
    return drawable and attr(relay, "outserv", 0) == 0


def main():
    try:
        app.GetOutputWindow().Clear()
    except Exception:
        pass

    relays = []
    for name, term, colour, style, width in RELAYS:
        r = relay_at(name, term)
        if r is None:
            out("%s: no relay of that name at terminal %s - run Configure_Reclosers.py" % (
                name, term))
            continue
        if not report(r):
            out("    -> %s has no in-service stage with a curve and will not be drawn" % name)
        relays.append((r, colour, style, width))
    if not relays:
        return

    board = app.GetGraphicsBoard()
    if board is None:
        out("No graphics board - open the project's single-line diagram first")
        return
    page = board.GetPage(PAGE, 1, "SetVipage")
    plot = page.GetOrInsertPlot(PLOT, "VisOcplot", 1)
    if plot is None:
        out("Could not create a time-overcurrent plot on page %s" % PAGE)
        return
    plot.Clear()
    for r, colour, style, width in relays:
        plot.AddRelay(r, colour, style, width)
    plot.Refresh()
    board.Show(page)
    out("Plotted %d relays on page '%s'" % (len(relays), PAGE))


main()
