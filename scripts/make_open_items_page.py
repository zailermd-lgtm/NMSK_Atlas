#!/usr/bin/env python3
"""Render docs/OPEN_ITEMS_FOR_OWNER.md into one self-contained RTL HTML page (published as the owner's open-items artifact).
    python3 scripts/make_open_items_page.py OUT.html"""
import html, re, sys
from pathlib import Path
src = (Path(__file__).resolve().parents[1] / "docs/OPEN_ITEMS_FOR_OWNER.md").read_text(encoding="utf-8")

def inline(s):
    s = html.escape(s)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", s)

out, lines, i = [], src.splitlines(), 0
title = "נושאים הדורשים מענה"
while i < len(lines):
    ln = lines[i]
    if ln.startswith("# "):
        title = ln[2:].strip(); i += 1
    elif ln.startswith("## "):
        out.append(f"<h2>{inline(ln[3:])}</h2>"); i += 1
    elif ln.startswith("|"):
        rows = []
        while i < len(lines) and lines[i].startswith("|"):
            cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            if not all(set(c) <= set("-: ") for c in cells): rows.append(cells)
            i += 1
        h, body = rows[0], rows[1:]
        t = "<div class='tw'><table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in h) + "</tr></thead><tbody>"
        for r in body:
            t += "<tr>" + "".join(f"<td data-l='{html.escape(h[k])}'>{inline(c)}</td>" for k, c in enumerate(r)) + "</tr>"
        out.append(t + "</tbody></table></div>")
    elif ln.startswith("- "):
        items = []
        while i < len(lines) and lines[i].startswith("- "):
            items.append(f"<li>{inline(lines[i][2:])}</li>"); i += 1
        out.append("<ul>" + "".join(items) + "</ul>")
    elif ln.strip():
        out.append(f"<p>{inline(ln)}</p>"); i += 1
    else:
        i += 1
page = f"""<title>נושאים פתוחים</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>
/* layout: one narrow reading column, tables collapse to labelled rows on phones */
:root{{--bg:#f6f5f2;--fg:#1d2127;--mut:#5b6470;--line:#d9d6cf;--acc:#0b6e69;--cardbg:#fffefb;--codebg:#ebe8e1}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#14181c;--fg:#e8e6e1;--mut:#9aa3ad;--line:#2c333a;--acc:#5fc4bb;--cardbg:#1b2026;--codebg:#252b32;color-scheme:dark}}}}
:root[data-theme="dark"]{{--bg:#14181c;--fg:#e8e6e1;--mut:#9aa3ad;--line:#2c333a;--acc:#5fc4bb;--cardbg:#1b2026;--codebg:#252b32;color-scheme:dark}}
html{{direction:rtl}}
body{{background:var(--bg);color:var(--fg);font:15px/1.6 "Heebo",system-ui,-apple-system,"Segoe UI",Arial,sans-serif;padding-block:24px 48px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}}
main{{max-width:980px;margin-inline:auto}}
h1{{font-size:1.6rem;margin:0 0 4px;text-wrap:balance}}
h2{{font-size:1.1rem;margin:32px 0 10px;padding-bottom:6px;border-bottom:2px solid var(--acc);text-wrap:balance}}
p{{margin:6px 0;color:var(--mut)}}
ul{{margin:8px 0;padding-inline-start:20px}} li{{margin:4px 0}}
code{{background:var(--codebg);padding:1px 5px;border-radius:4px;font:0.88em ui-monospace,Menlo,Consolas,monospace;direction:ltr;unicode-bidi:isolate;overflow-wrap:anywhere}}
.tw{{overflow-x:auto;background:var(--cardbg);border:1px solid var(--line);border-radius:8px}}
table{{border-collapse:collapse;width:100%}}
th,td{{text-align:start;vertical-align:top;padding:9px 11px;border-bottom:1px solid var(--line)}}
th{{font-size:.8rem;color:var(--mut);letter-spacing:.02em;white-space:nowrap}}
tr:last-child td{{border-bottom:0}} td:first-child{{width:2.2em;color:var(--mut)}} td:nth-child(2){{font-weight:600}}
@media (max-width:640px){{thead{{display:none}} table,tbody,tr,td{{display:block;width:auto}} tr{{padding:8px 4px;border-bottom:1px solid var(--line)}} tr:last-child{{border-bottom:0}} td{{border:0;padding:3px 9px}} td:first-child{{width:auto}} td::before{{content:attr(data-l) ": ";color:var(--mut);font-size:.8rem;font-weight:400}} td:nth-child(2)::before{{content:""}}}}
</style>
<main><h1>{inline(title)}</h1>{''.join(out)}</main>"""
Path(sys.argv[1]).write_text(page, encoding="utf-8")
print("wrote", sys.argv[1], len(page))
