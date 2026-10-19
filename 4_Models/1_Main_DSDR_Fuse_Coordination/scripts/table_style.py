"""
Spreadsheet-style tables for the report: every cell framed (vertical and horizontal lines), no shaded
header row, bold header text.  Applied to the finished LaTeX source by make_report_latex.py.
"""

import re

ENV = re.compile(r"\\begin\{(tabularx?)\}(\{\\(?:text|line)width\})?\{", re.S)


def _balanced(s, i):
    """index after the brace group that starts at s[i] == '{'"""
    depth = 0
    for k in range(i, len(s)):
        if s[k] == "{":
            depth += 1
        elif s[k] == "}":
            depth -= 1
            if depth == 0:
                return k + 1
    raise ValueError("unbalanced braces")


def _columns(spec):
    """split a column specification into column tokens (l, c, r, X, L, p{..}, >{..}x); drop @{..}"""
    out, i = [], 0
    while i < len(spec):
        ch = spec[i]
        if ch in " |":
            i += 1
        elif ch == "@":
            i = _balanced(spec, i + 1)
        elif ch == "*":
            j = _balanced(spec, i + 1)
            n = int(spec[i + 2:j - 1])
            k = _balanced(spec, j)
            out += _columns(spec[j + 1:k - 1]) * n
            i = k
        elif ch == ">":
            j = _balanced(spec, i + 1)
            tok, i = spec[i:j], j
            if spec[i] in "pmb":
                k = _balanced(spec, i + 1)
                tok, i = tok + spec[i:k], k
            else:
                tok, i = tok + spec[i], i + 1
            out.append(tok)
        elif ch in "pmb" and i + 1 < len(spec) and spec[i + 1] == "{":
            k = _balanced(spec, i + 1)
            out.append(spec[i:k])
            i = k
        else:
            out.append(ch)
            i += 1
    return out


def _body(body):
    body = re.sub(r"\\toprule\s*", r"\\hline\n", body)
    body = re.sub(r"\\(midrule|bottomrule)\s*", "", body)
    # vertical line on the right of every multicolumn
    body = re.sub(r"\\multicolumn\{(\d+)\}\{([lcr])\}", lambda m: r"\multicolumn{%s}{%s|}" % m.groups(), body)
    # a horizontal line under every row; a header that spans two rows (marked \hd) is kept as one block
    rows = re.split(r"(\\\\[ \t]*(?:\n|$))", body)
    out = []
    for k in range(0, len(rows) - 1, 2):
        row, sep = rows[k], rows[k + 1]
        nxt = rows[k + 2] if k + 2 < len(rows) else ""
        header_continues = "\\hd" in row and "\\hd" in nxt
        out.append(row + ("\\\\\n" if header_continues else "\\\\ \\hline\n"))
    out.append(rows[-1] if len(rows) % 2 else "")
    return "".join(out).replace("\\hd", "")


def excel_tables(tex):
    out, pos = [], 0
    for m in ENV.finditer(tex):
        if m.start() < pos:
            continue
        spec_start = m.end() - 1
        spec_end = _balanced(tex, spec_start)
        spec = tex[spec_start + 1:spec_end - 1]
        env = m.group(1)
        end = tex.index("\\end{%s}" % env, spec_end)
        if tex.startswith("%plain", spec_end):          # a list without frame (symbols, abbreviations)
            out.append(tex[pos:end])
            pos = end
            continue
        cols = _columns(spec)
        new_spec = "|" + "|".join(cols) + "|"
        out.append(tex[pos:m.start()])
        out.append(tex[m.start():spec_start] + "{" + new_spec + "}")
        out.append(_body(tex[spec_end:end]))
        pos = end
    out.append(tex[pos:])
    return "".join(out)
