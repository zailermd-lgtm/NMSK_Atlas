"""Q218: the artifact service wraps a published page in a document skeleton; a build dir that was restored from the published artifact
carries it. unwrap() returns the page as the builder wrote it (raw dirs pass through unchanged)."""
import re

_PRE = re.compile(r'\A<!doctype html><html><head><meta charset=utf8><meta name=viewport content="[^"]*"><style>.*?</style></head><body>\n', re.S)
_SUF = "\n</body></html>"


def unwrap(html: str) -> str:
    m = _PRE.match(html)
    if m and html.endswith(_SUF):
        return html[m.end():-len(_SUF)]
    return html
