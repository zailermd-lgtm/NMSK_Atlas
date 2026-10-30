#!/usr/bin/env python3
"""Q239 -- paste the owner's imaging + ultrasound add-on code and tissue tables INTO a built viewer page (build step; the public templates are not touched).

Why: on the published (artifact-hosted) pages the add-ons were four SIBLING files (clinical_imaging_tool.js, clinical_imaging_tissues.json,
clinical_ultrasound_tool.js, clinical_ultrasound_tissues.json). Any hosting difference for a sibling (a script refused for its MIME type, a file not uploaded, a
404 swallowed as "optional", a page answering instead of the file) left the plain atlas with NO trace of the tools. Pasted into the page they cannot go missing; the
files beside the page stay as a fallback (the tools read the pasted table first and fetch the file only when it is absent; a second load of the code is ignored).

    inline_into(html_text, imaging=True, ultrasound=True, clinical=CLINICAL) -> html_text     (idempotent: an earlier block is replaced)
    uninline(html_text) -> html_text                                                          (exactly the page before inlining: the template's hook line is restored)
    status(html_text) -> {"imaging": bool, "ultrasound": bool}

The block replaces the template's generic hook line <script src="clinical_imaging_tool.js"></script>, so it still runs after the needle hook line and chains onto it.
NOT inlined (separate, optional files): needle tool, risk tables, motor points."""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CLINICAL = REPO / "clinical"
HOOK_RE = re.compile(r'^<script src="clinical_imaging_tool\.js"></script>[^\n]*$', re.M)
BEGIN_RE = re.compile(r"<!-- NMSK_INLINE_IMAGING begin (\{.*?\}) -->\n.*?<!-- NMSK_INLINE_IMAGING end -->", re.S)


def _js(text: str) -> str:
    out = re.sub(r"</(script)", r"<\\/\1", text, flags=re.I)
    out = out.replace("<!--", "<\\!--")
    assert not re.search(r"</script|<!--", out, re.I)
    return out


def _json(text: str) -> str:
    json.loads(text)                                              # must be valid before it goes into a page
    out = re.sub(r"</(script)", r"<\\/\1", text, flags=re.I).replace("<!--", "<\\u0021--")
    assert not re.search(r"</script|<!--", out, re.I)
    json.loads(out)
    return out


def uninline(html: str) -> str:
    def back(m):
        return json.loads(m.group(1))["hook"]
    return BEGIN_RE.sub(back, html)


def status(html: str) -> dict:
    return {"imaging": 'id="nmsk-imaging-inline"' in html, "ultrasound": 'id="nmsk-ultrasound-inline"' in html}


def inline_into(html: str, imaging: bool = True, ultrasound: bool = True, clinical: Path = CLINICAL) -> str:
    html = uninline(html)
    hooks = HOOK_RE.findall(html)
    if len(hooks) != 1:
        raise SystemExit(f"page: expected exactly one imaging hook line, found {len(hooks)}")
    if not imaging:
        return html
    parts = ['<!-- NMSK_INLINE_IMAGING begin %s -->' % json.dumps({"hook": hooks[0], "q": "q239"}).replace("<", "\\u003c").replace(">", "\\u003e")]
    parts.append('<script type="application/json" id="nmsk-imaging-tissues">%s</script>' % _json((clinical / "data" / "imaging_tissues.json").read_text(encoding="utf-8")))
    if ultrasound:
        parts.append('<script type="application/json" id="nmsk-ultrasound-tissues">%s</script>' % _json((clinical / "data" / "ultrasound_tissues.json").read_text(encoding="utf-8")))
    parts.append('<script id="nmsk-imaging-inline">\n%s\n</script>' % _js((clinical / "imaging_tool.js").read_text(encoding="utf-8")))
    if ultrasound:
        parts.append('<script id="nmsk-ultrasound-inline">\n%s\n</script>' % _js((clinical / "ultrasound_tool.js").read_text(encoding="utf-8")))
    parts.append("<!-- NMSK_INLINE_IMAGING end -->")
    block = "\n".join(parts)
    return HOOK_RE.sub(lambda m: block, html, count=1)


def inline_file(path: Path, imaging: bool = True, ultrasound: bool = True, clinical: Path = CLINICAL) -> bool:
    path = Path(path)
    old = path.read_text(encoding="utf-8")
    new = inline_into(old, imaging, ultrasound, clinical)
    if new != old:
        path.write_text(new, encoding="utf-8")
    return new != old


def inline_dir(build_dir: Path, ultrasound: bool = True, clinical: Path = CLINICAL) -> list[Path]:
    """every page html of a build dir (atlas_viewer*.html and index.html)"""
    done = []
    for p in sorted(Path(build_dir).glob("*.html")):
        t = p.read_text(encoding="utf-8")
        if HOOK_RE.search(t) or BEGIN_RE.search(t):
            inline_file(p, True, ultrasound, clinical)
            done.append(p)
    return done
