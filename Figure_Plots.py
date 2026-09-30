"""
Time-overcurrent plots of Figs. 8, 9, 11, 12, 13 and 16 of Yousaf et al. (2022), drawn by
PowerFactory itself.

For each figure the script
  1. creates (or rebuilds) a plot page "Fig 8", "Fig 9", ... with the figure's reclosers and
     fuses, axes 100-100 000 A and 0.01-1000 s as in the paper;
  2. executes the figure's fault (location, type, phases, Rf; Complete method) with the DG in
     service, so the plot shows the fault-current lines and trip times, and keeps it as a
     short-circuit command "Fault Fig 8", ... in the study case;
  3. exports the page to Result\\PF_Figures\\Fig08.png, ...

Only the last fault stays calculated. To see another figure's lines again, execute its
"Fault Fig ..." command in the study case (the DG must be in service).

Fig. 15 (R2 as dual-setting recloser) is not drawn: the reverse setting of R2 is not in the
model. Figs. 7, 14, 17 are not time-overcurrent plots (see Result\\Figures and
Fig14_Coordination.py).

Run: Python Script (ComPython) in the study case -> Execute, with the single-line diagram
open. Also called by Show_Progress.py.
"""

import os

import powerfactory as pf

OUT_DIR = r"D:\Protection and co-ordination\Result\PF_Figures"
R1 = [("R1", "RG60"), ("R1 Delayed", "RG60")]
R2 = [("R2", "671"), ("R2 Delayed", "671")]
# page, title, devices (relays as (name, terminal), fuses by name), fault location
# (node, or (line, % from its bus1 end)), fault type, Rf (ohm)
FIGURES = [
    ("Fig 8", "SLG fault at node 611", R2 + ["F684", "F671-2"], "611", "LG", 0.0),
    ("Fig 9", "LLG fault at mid 692-675, Rf 1 ohm", R2 + ["F692-R", "F671-1"],
     ("LC692-675", 50.0), "LLG", 1.0),
    ("Fig 11", "LL fault at node 646, Rf 1 ohm", R1 + ["F646", "F632"], "646", "LL", 1.0),
    ("Fig 12", "LL fault at node 645, Rf 1.5 ohm", R2 + ["F646", "F632"], "645", "LL", 1.5),
    ("Fig 13", "3-phase fault at 10 % of line 632-633", R2 + ["F633"],
     ("LOHL632-633", 10.0), "LLL", 0.0),
    ("Fig 16", "solid LL fault at node 646", R1 + ["F646", "F632"], "646", "LL", 0.0),
]
# PowerFactory colour index per device position: fast, delayed, fuse 1, fuse 2
COLOURS = [4, 2, 3, 6]
COLOUR_NAMES = ["blue", "red", "green", "cyan"]
# the paper's times for the same figure, printed in the image title
PAPER = {"Fig 8": "R2 fast 0.207 s, F684 0.476 s, F671-2 1.456 s, R2 delayed 2.472 s",
         "Fig 9": "R2 fast 0.141 s, fuses 0.217 s / 0.546 s, R2 delayed 1.483 s",
         "Fig 11": "R1 fast 0.134 s, F646 0.202 s, F632 1.096 s, R1 delayed 2.690 s",
         "Fig 12": "R2 fast 0.419 s, R2 delayed 16.683 s, F632 25.440 s",
         "Fig 13": "R2 fast 0.079 s, R2 delayed 1.556 s, F633 0.022 s",
         "Fig 16": "R1 fast 0.128 s, F646 0.181 s, F632 0.411 s, R1 delayed 2.555 s"}
KIND = {"LG": ("spgf", "i_pspgf"), "LL": ("2psc", "i_p2psc"),
        "LLG": ("2pgf", "i_p2pgf"), "LLL": ("3rst", None)}
AXES = dict(x_min=100.0, x_max=100000.0, y_min=0.01, y_max=1000.0)
CUBICLE_KEYS = ("bus1", "bus2", "bushv", "buslv")
PHASES = ("A", "B", "C")

try:
    app            # one shared Application when loaded by Show_Progress.py
except NameError:
    app = pf.GetApplication()


def out(s=""):
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
    except Exception:
        return False


def find_device(d):
    if isinstance(d, tuple):
        name, term = d
        for r in app.GetCalcRelevantObjects("%s.ElmRelay" % name):
            if attr(attr(r.GetParent(), "cterm"), "loc_name") == term:
                return r
        return None
    found = app.GetCalcRelevantObjects("%s.RelFuse" % d)
    return found[0] if found else None


def device_current(dev):
    """Largest phase current (A) at the device's cubicle after a short circuit."""
    cub = dev.GetParent()
    el = attr(cub, "obj_id")
    for k in CUBICLE_KEYS:
        if el is not None and attr(el, k) == cub:
            return 1000.0 * max(abs(attr(el, "m:Ikss:%s:%s" % (k, p), 0.0)) for p in PHASES)
    return 0.0


def save_command(page, shc):
    """Keep the figure's fault as command 'Fault <page>' in the study case (a copy of the
    study case's short-circuit command as set up for this figure)."""
    case = app.GetActiveStudyCase()
    name = "Fault " + page
    for old in case.GetContents(name + ".ComShc"):
        old.Delete()
    return case.AddCopy(shc, name) is not None


def apply_fault(cmd, loc, ftype, rf, devs):
    """Set up and execute the fault; with several possible phases (pairs) keep the one
    with the largest current through the plotted devices, and leave it calculated."""
    terms = {t.loc_name: t for t in app.GetCalcRelevantObjects("*.ElmTerm")}
    lines = {l.loc_name: l for l in app.GetCalcRelevantObjects("*.ElmLne")}
    kind, sel = KIND[ftype]
    cmd.iopt_mde = 3                                   # Complete method
    cmd.iopt_allbus = 0
    if isinstance(loc, tuple):
        cmd.shcobj = lines[loc[0]]
        cmd.ppro = loc[1]
    else:
        cmd.shcobj = terms[loc]
    cmd.iopt_shc = kind
    cmd.Rf = rf
    cmd.Xf = 0.0
    best, best_i = None, -1.0
    app.EchoOff()
    try:
        for p in ([None] if sel is None else range(3)):
            if sel is not None:
                setattr_ok(cmd, sel, p)
            if cmd.Execute() != 0:
                continue
            i = max(device_current(d) for d in devs)
            if i > best_i:
                best, best_i = p, i
        if best is not None and sel is not None:
            setattr_ok(cmd, sel, best)
        ok = best_i > 0 and cmd.Execute() == 0      # leave the chosen fault calculated
    finally:
        app.EchoOn()
    return ok, best


def export(page, path):
    """Save the shown page as PNG (Save File command); WMF if PNG is not possible."""
    wr = app.GetFromStudyCase("ComWr")
    if wr is not None:
        setattr_ok(wr, "iopt_rd", "png")
        setattr_ok(wr, "f", path + ".png")
        if wr.Execute() == 0 and os.path.exists(path + ".png"):
            return path + ".png"
    board = app.GetGraphicsBoard()
    if board is not None and board.WriteWMF(path) == 0:
        return path + ".wmf"
    return None


def plot_page(board, name):
    """Page 'name' with its time-overcurrent plot: the plot already on the page if there is
    one; otherwise inserted; if that fails the page is removed and built again."""
    page = board.GetPage(name, 1, "SetVipage")
    if page is None:
        return None, None
    found = page.GetContents("*.VisOcplot", 1)
    if found:
        return page, found[0]
    plot = page.GetOrInsertPlot("TCC", "VisOcplot", 1)
    if plot is not None:
        return page, plot
    board.RemovePage(page)                          # rebuild a page that cannot take a plot
    page = board.GetPage(name, 1, "SetVipage")
    if page is None:
        return None, None
    return page, page.GetOrInsertPlot("TCC", "VisOcplot", 1)


def page_title(page_name, title):
    """Descriptive page name, e.g. 'Fig 16 - solid LL fault at node 646' (only characters
    PowerFactory accepts in object names)."""
    import re
    text = "%s - %s" % (page_name, title.replace("%", "pct"))
    text = re.sub(r"(\d)\.(\d)", r"\1p\2", text)        # 1.5 -> 1p5 ('.' not allowed)
    return "".join(c for c in text if c.isalnum() or c in " -()")


def legend_line(devs):
    """'R1: blue = fast, red = delayed | F646: green band | F632: cyan band'."""
    parts, k = [], 0
    rec = [d for d in devs if d.GetClassName() == "ElmRelay"]
    if rec:
        parts.append("%s: %s = fast, %s = delayed" % (
            rec[0].loc_name, COLOUR_NAMES[0], COLOUR_NAMES[1]))
        k = len(rec)
    for i, d in enumerate(devs[k:]):
        parts.append("%s: %s band" % (d.loc_name, COLOUR_NAMES[(k + i) % len(COLOUR_NAMES)]))
    return "   |   ".join(parts) + "   (fuse band: melting to clearing time)"


def add_banner(path, lines):
    """Put a title banner above an exported PNG (needs Pillow; skipped without it)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False
    img = Image.open(path).convert("RGB")
    w = img.width
    size = max(14, w // 60)
    try:
        bold = ImageFont.truetype("arialbd.ttf", int(size * 1.35))
        font = ImageFont.truetype("arial.ttf", size)
    except OSError:
        bold = font = ImageFont.load_default()
    pad, gap = size, int(size * 0.5)
    fonts = [bold] + [font] * (len(lines) - 1)
    heights = [f.getbbox("Ag")[3] for f in fonts]
    top = pad * 2 + sum(heights) + gap * (len(lines) - 1)
    out_img = Image.new("RGB", (w, img.height + top), "white")
    out_img.paste(img, (0, top))
    draw = ImageDraw.Draw(out_img)
    y = pad
    for text, f, h in zip(lines, fonts, heights):
        draw.text((pad, y), text, fill=(11, 11, 11) if f is bold else (60, 60, 58), font=f)
        y += h + gap
    draw.line([(0, top - 2), (w, top - 2)], fill=(200, 200, 200), width=2)
    out_img.save(path)
    return True


def main(clear=True):
    if clear:
        try:
            app.GetOutputWindow().Clear()
        except Exception:
            pass
    board = app.GetGraphicsBoard()
    if board is None:
        out("No graphics board: open the single-line diagram first, then run again.")
        return
    os.makedirs(OUT_DIR, exist_ok=True)
    for r in app.GetCalcRelevantObjects("R1.ElmRelay"):       # feeder breaker must be closed
        for sw in r.GetParent().GetContents("*.StaSwitch"):
            if attr(sw, "on_off") == 0:
                sw.on_off = 1
                out("Breaker in the R1 cubicle was OPEN - closed")
    dgs = app.GetCalcRelevantObjects("*.ElmSym")
    for g in dgs:
        if attr(g, "outserv") == 1:
            g.outserv = 0
            out("DG %s put in service (the figures are with the DG)." % g.loc_name)

    for page_name, title, names, loc, ftype, rf in FIGURES:
        devs = [find_device(d) for d in names]
        missing = [str(d) for d, x in zip(names, devs) if x is None]
        if missing:
            out("%-7s not drawn: device(s) not found: %s" % (page_name, ", ".join(missing)))
            continue
        full_name = page_title(page_name, title)
        old = board.GetPage(page_name, 0)           # short-named page of an earlier run
        if old is not None and old.loc_name != full_name:
            board.RemovePage(old)
        page, plot = plot_page(board, full_name)
        if plot is None:
            out("%-7s could not create the plot (page class %s)" % (
                page_name, page.GetClassName() if page is not None else "none"))
            continue
        plot.Clear()
        for k, d in enumerate(devs):
            plot.AddRelay(d, COLOURS[k % len(COLOURS)], 1, 2)
        for a, v in AXES.items():
            setattr_ok(plot, a, v)
        # the study case's own command, so the page's title block names this fault
        shc = app.GetFromStudyCase("ComShc")
        ok, phase = apply_fault(shc, loc, ftype, rf, devs)
        saved_cmd = save_command(page_name, shc)
        board.Show(page)
        app.Rebuild()
        currents = ", ".join("%s %.0f A" % (d.loc_name, device_current(d)) for d in devs
                             if not d.loc_name.endswith(" Delayed"))
        where = "%s at %g %%" % loc if isinstance(loc, tuple) else "node %s" % loc
        if not ok:
            out("%-7s %s: short circuit FAILED - plot drawn without fault currents" % (
                page_name, title))
            continue
        saved = export(page, os.path.join(OUT_DIR, "Fig%02d" % int(page_name.split()[1])))
        if saved and saved.endswith(".png"):
            add_banner(saved, [
                "Fig. %s (PowerFactory model) - %s, DG in service" % (
                    page_name.split()[1], title),
                legend_line(devs),
                "Fault current: %s   |   Paper: %s" % (currents, PAPER[page_name])])
        out("%-7s %s (%s, %s%s, Rf %.1f ohm)" % (
            page_name, title, where, ftype,
            "" if phase is None else ", phase option %d" % phase, rf))
        out("        currents: %s" % currents)
        out("        page '%s', command %s, image %s" % (
            full_name, ("'Fault %s'" % page_name) if saved_cmd else "NOT SAVED",
            saved or "NOT SAVED"))
    out("")
    out("Each page shows its fault lines right after it is drawn; only the last fault stays")
    out("calculated. Execute 'Fault Fig ..' in the study case to show another figure's lines.")


if __name__ == "__main__":
    main()
