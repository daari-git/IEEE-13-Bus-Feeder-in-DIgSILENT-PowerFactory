"""
Operating-time curves, identical to the PowerFactory library types (data from studies.json):

  R1  GE IAC77B801A   IAC extremely inverse GES7005B (formula), curve from 1.5 x Ip to 40 x Ip
  R2  GE/Alstom CDG34 CDG14 extremely inverse 398.S23.37 (table of t vs M for TMS 0.1-1.0),
                      curve from 2 x Is to 40 x Is, t >= 0.031 s at any TMS
  fuses               minimum melting (MMT) and total clearing (TCT) tables of the library type
Times are in s, currents in primary A.  A current below a curve's start returns inf (no trip).
"""

import math

INF = float("inf")


def _loglog(x, pts):
    """Log-log interpolation in a sorted list of (x, y); None outside the range."""
    if x < pts[0][0] or x > pts[-1][0]:
        return None
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if x1 <= x <= x2:
            if x2 == x1:
                return y1
            f = (math.log(x) - math.log(x1)) / (math.log(x2) - math.log(x1))
            return math.exp(math.log(y1) + f * (math.log(y2) - math.log(y1)))
    return pts[-1][1]


class IAC:
    """IAC extremely inverse: t = TDS (0.004 + 0.6379/(M-0.62) + 1.7872/(M-0.62)^2 + 0.2461/(M-0.62)^3)."""

    def __init__(self, data):
        self.imin, self.imax = data["imin"], data["imax"]

    def t(self, i, ip, tds):
        m = i / ip
        if m < self.imin:
            return INF
        x = min(m, self.imax) - 0.62
        return tds * (0.004 + 0.6379 / x + 1.7872 / x ** 2 + 0.2461 / x ** 3)


class CDG:
    """CDG14 extremely-inverse table, log-log in M, linear in TMS (extrapolated below 0.1)."""

    def __init__(self, data):
        rows = data["vmat"]
        self.tms = rows[0][1:]
        self.rows = rows[1:]
        self.imin, self.imax, self.tmin = data["imin"], data["imax"], data["tmin"]

    def t(self, i, ip, tms):
        m = i / ip
        if m < self.imin:
            return INF
        m = min(m, self.imax)
        col = [_loglog(m, [(r[0], r[j + 1]) for r in self.rows]) for j in range(len(self.tms))]
        k = max(0, min(len(self.tms) - 2, next((j for j in range(len(self.tms) - 1)
                                                if tms <= self.tms[j + 1]), len(self.tms) - 2)))
        f = (tms - self.tms[k]) / (self.tms[k + 1] - self.tms[k])
        return max(self.tmin, col[k] + f * (col[k + 1] - col[k]))    # tmin is absolute (as in PF)


class Fuse:
    def __init__(self, data):
        m = data["vmat"]
        self.irat = data["irat"]
        self.melt = sorted((r[0], r[1]) for r in m if r[0] > 0)
        self.clear = sorted((r[2], r[3]) for r in m if r[2] > 0)

    @staticmethod
    def _t(pts, i):
        if i < pts[0][0]:
            return INF
        if i > pts[-1][0]:
            return pts[-1][1]
        return _loglog(i, pts)

    def mmt(self, i):
        return self._t(self.melt, i)

    def tct(self, i):
        return self._t(self.clear, i)

    def i_at_mmt(self, t):
        """Current that melts the fuse in t seconds."""
        pts = sorted((b, a) for a, b in self.melt)
        return _loglog(t, pts)
