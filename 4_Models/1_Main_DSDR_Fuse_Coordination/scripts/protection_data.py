"""
Protection data of the IEEE 13-node feeder (Fig. 6 of Yousaf et al. 2022) and the paper's
published values, used by every other script.

Sources for device data the 2022 paper does not print:
  [8]  M. Yousaf, K. M. Muttaqi, D. Sutanto, "Overcurrent protection scheme for the IEEE 13-node
       benchmark test feeder with improved selectivity", IEEE PES GM 2020, Table V
       (Gould-Shawmut A055C fuses, GE IAC recloser, GE/Alstom CDG relay, gL-800 LV fuse).
  Figs. 8, 9, 11, 12, 13, 15, 16 of the 2022 paper: fuse bands digitised and matched to the
       A055C library curves (melting current at 100 s / 1000 s, within 2 %); used for every
       fuse that a figure shows (F632, F633, F646, F671-1, F671-2, F684, F692, F692-R).
"""

# --------------------------------------------------------------------------------------------
# Device locations.  ("line", name, side)  -> cubicle of branch `name` at `side` (bus1/bus2/buslv)
#                    ("load", name)        -> cubicle of load `name`
# --------------------------------------------------------------------------------------------
# Fuse sizes: the size drawn in the 2022 paper's own figures where a figure shows the fuse (bands
# digitised and matched to the A055C library curves), otherwise ref. [8] Table V.  The figure sizes
# take precedence because they are what the 2022 results were produced with: with [8]'s smaller
# F671-2 (200E) the fuse melts in the second fast shot of Fig. 10 (0.62 s) instead of after both
# shots (paper 1.21 s; 300E gives 1.25 s).  The two papers name some devices differently
# ([8] Fig. 1 against Fig. 6 of the 2022 paper):
#   [8] REC1, REC2  = reclosers R1, R2 of the 2022 paper
#   [8] R1, R2, R5  = overcurrent relays at 632 and 671 - not used in the 2022 scheme, neglected
#   [8] F671        = fuse at 671 towards 684            -> F671-2 here
#   [8] F671-R      = fuse of the load L671              -> F671 here
#   F632 (632-645) and F671-1 (671-692) replace [8]'s relays R1 and R5; they are not in [8], so
#   their sizes come from the fuse bands of the 2022 paper's figures.
#   [8] also fuses the capacitors (F-C611 50E, F-C675 125E); Fig. 6 of the 2022 paper has no
#   capacitor fuses, so they are not modelled.
FUSES = {
    #  name      location                              library type   source of the size
    "F632":   (("line", "LOHL632-645", "bus1"),      "A055C400E", "2022 Figs. 12, 15, 16 (not in [8]: relay R1 there)"),
    "F633":   (("line", "LOHL632-633", "bus1"),      "A055C250E", "[8] Table V"),
    "F634":   (("line", "XFM-1", "buslv"),           "gL-800A",   "[8] Table V (IEC 60269 gL 800 A)"),
    "F645":   (("load", "L645-YcPQ"),                "A055C250E", "[8] Table V"),
    "F646":   (("line", "LOHL645-646", "bus1"),      "A055C300E", "2022 Figs. 11, 15, 16 ([8]: 200E)"),
    "F-DL":   (("line", "LDL", "bus1"),              "A055C250E", "[8] Table V"),
    "F671":   (("load", "L571-DcPQ"),                "A055C250E", "[8] Table V (F671-R there)"),
    "F671-1": (("line", "Switch", "bus1"),           "A055C300E", "2022 Fig. 9 (not in [8]: relay R5 there)"),
    "F692":   (("load", "L692-DcI"),                 "A055C200E", "[8] Table V"),
    "F692-R": (("line", "LC692-675", "bus1"),        "A055C250E", "2022 Fig. 9 ([8]: 300E)"),
    "F675":   (("load", "L675-YcPQ"),                "A055C200E", "[8] Table V"),
    "F671-2": (("line", "LOHL671-684", "bus1"),      "A055C300E", "2022 Fig. 8 ([8]: 200E, F671 there)"),
    "F684":   (("line", "LOHL684-611", "bus1"),      "A055C200E", "2022 Fig. 8 ([8]: 150E)"),
    "F611":   (("load", "L611-YcI"),                 "A055C125E", "[8] Table V"),
    "F652":   (("line", "LC684-652A", "bus1"),       "A055C150E", "[8] Table V"),
}

# Reclosers.  R1: feeder recloser (GE IAC77B801A, extremely inverse, TDS 0.5 / 10 - paper).
#             R2: mid-line recloser on 632-671 at the 671 end (GE/Alstom CDG34, extremely inverse).
RECLOSERS = {
    "R1": dict(loc=("line", "LOHL650-632", "bus1"), relay="IAC77B801A", ct=900.0),
    "R2": dict(loc=("line", "LOHL632-671end", "bus2"), relay="CDG34", ct=500.0),
}
R2_UNITS = ["R2 Fast", "R2 Delayed", "R2 Rev Fast", "R2 Rev Delayed"]

# Distributed load: the middle lump is moved behind a short lateral nDL - DL so that a fault at
# "DL" lies below fuse F-DL, as drawn in Fig. 6.
DL_LUMP = "DistributedLoad"

# --------------------------------------------------------------------------------------------
# Fault locations of Figs. 14 / 17 and Table IV.  Nodes upstream of R2 are in R1's zone.
# phases: conductors present at the node.  primary: fuse feeding the node (Table IV "Fuse").
# path: fuses in series from the fault towards the source (primary first).
# --------------------------------------------------------------------------------------------
NODES = {
    "632": dict(phases="ABC", zone="R1", path=[]),
    "633": dict(phases="ABC", zone="R1", path=["F633"]),
    "634": dict(phases="ABC", zone="R1", path=["F634", "F633"], lv=True),
    "645": dict(phases="BC",  zone="R1", path=["F632"]),
    "646": dict(phases="BC",  zone="R1", path=["F646", "F632"]),
    "DL":  dict(phases="ABC", zone="R1", path=["F-DL"]),
    "671": dict(phases="ABC", zone="R2", path=[]),
    "692": dict(phases="ABC", zone="R2", path=["F671-1"]),
    "675": dict(phases="ABC", zone="R2", path=["F692-R", "F671-1"]),
    "680": dict(phases="ABC", zone="R2", path=[]),
    "684": dict(phases="AC",  zone="R2", path=["F671-2"]),
    "652": dict(phases="A",   zone="R2", path=["F652", "F671-2"]),
    "611": dict(phases="C",   zone="R2", path=["F684", "F671-2"]),
}
NODE_ORDER = ["632", "633", "634", "645", "646", "671", "692", "675", "680", "684", "652", "611", "DL"]
FAULT_TYPES = ["LG", "LL", "LLG", "LLL"]
PF_FAULT = {"LG": "spgf", "LL": "2psc", "LLG": "2pgf", "LLL": "3rst"}

# Branches of Table II:  label -> (branch, side of the measuring cubicle, downstream nodes)
TABLE2_BRANCHES = [
    ("RG60", "632",      "LOHL650-632", "bus1", ["632", "633", "645", "646", "DL", "671", "692", "675", "680", "684", "652", "611"]),
    ("632", "633",       "LOHL632-633", "bus1", ["633"]),
    ("632", "645",       "LOHL632-645", "bus1", ["645", "646"]),
    ("632", "671",       "LOHL632-671end", "bus2", ["671", "692", "675", "680", "684", "652", "611"]),
    ("XFM1-HV", "side",  "XFM-1", "bushv", ["634"]),
    ("XFM1-LV", "side",  "XFM-1", "buslv", ["634"]),
    ("645", "646",       "LOHL645-646", "bus1", ["646"]),
    ("671", "692",       "Switch", "bus1", ["692", "675"]),
    ("671", "684",       "LOHL671-684", "bus1", ["684", "652", "611"]),
    ("671", "680",       "LOHL671-680", "bus1", ["680"]),
    ("692", "675",       "LC692-675", "bus1", ["675"]),
    ("684", "611",       "LOHL684-611", "bus1", ["611"]),
    ("684", "652",       "LC684-652A", "bus1", ["652"]),
]

# --------------------------------------------------------------------------------------------
# Published values (for comparison only)
# --------------------------------------------------------------------------------------------
PAPER_TABLE2 = {  # (from, to): (Inom A, If,min kA, If,max kA)
    ("RG60", "632"): (587.1, 1.24, 5.41), ("632", "633"): (81.1, 0.72, 6.73),
    ("632", "645"): (143.3, 0.93, 4.25), ("632", "671"): (478.2, 1.08, 4.52),
    ("XFM1-HV", "side"): (81.1, 0.73, 6.48), ("XFM1-LV", "side"): (704.7, 0.59, 18.76),
    ("645", "646"): (64.9, 0.84, 3.64), ("671", "692"): (229.3, 0.78, 3.69),
    ("671", "684"): (70.9, 0.69, 3.47), ("671", "680"): (0.0, 0.59, 6.25),
    ("692", "675"): (205.9, 0.71, 7.83), ("684", "611"): (70.8, 0.63, 1.93),
    ("684", "652"): (63.1, 0.66, 2.67),
}
PAPER_TABLE3 = {"F632": 6.38, "F633": 6.83, "F634": 8.32, "F645": 6.65, "F646": 6.67, "F-DL": 6.54,
                "F611": 6.19, "F692": 6.13, "F671": 6.08, "F671-1": 5.85, "F671-2": 5.87,
                "F652": 6.17, "F684": 6.15, "F675": 6.19, "F692-R": 6.14}
PAPER_TABLE4 = {  # node: (R1 fast, R1 delayed, R2 fast, R2 delayed, fuse MMT)
    "632": (0.070, 1.398, 0.045, 0.514, None), "633": (0.094, 1.880, 0.052, 0.706, 0.163),
    "645": (0.105, 2.095, 0.087, 1.659, 0.276), "646": (0.128, 2.555, 0.103, 2.046, 0.181),
    "DL": (0.087, 1.733, 0.076, 1.402, 0.248), "671": (0.105, 2.091, 0.068, 1.113, None),
    "692": (0.115, 2.307, 0.072, 1.258, 0.175), "675": (0.121, 2.414, 0.074, 1.332, 0.185),
    "684": (0.125, 2.507, 0.075, 1.394, 0.205), "680": (0.137, 2.747, 0.079, 1.555, None),
    "611": (0.326, 6.523, 0.146, 4.385, 0.417), "652": (0.676, 13.525, 0.143, 9.370, 0.233),
}
# Fig. 14 (without DSDR): cells marked "doesn't exist"; Fig. 17 (with DSDR): none.
PAPER_FIG14_LOST = {("633", "LLG"), ("633", "LLL"), ("645", "LG"), ("645", "LL"), ("645", "LLG"),
                    ("646", "LL"), ("646", "LLG"), ("675", "LLG"), ("675", "LLL")}

OLF = 1.25            # overload factor, eqs. (3) and (12)
A_FUSE = -1.8         # fuse slope a_i, eq. (6)
T_RECL_MIN = 10 / 60  # minimum time delay between the reclosers' delayed curves (10 cycles)
