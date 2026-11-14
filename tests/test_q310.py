"""Q310: no script and no test may hard-code a build baseline that is not on disk.

This is the guard for the regression that made Q310 necessary. Q297's five shared helpers, Q298's three table
builders, Q299's containment fix and six test modules each carried a *literal* `build/q29x` as the default value
of their `--src` / `root` argument. Every one of them went on naming the build its own round had happened to run
on, long after a later round published a new baseline, so

  * the defaults were silently measuring superseded pages -- PROJECT_STATE Q299 E2 is the time that was caught,
    where the after-the-fix containment audit re-measured the pages it was meant to be checking, and
  * two 365 MB directories (`build/q296`, `build/q297`) could not be deleted without breaking the live pipeline,
    on a disk that was 99 % full.

The fix is that there is now exactly ONE place that records the current baseline --
`scripts/anatomy/q241/model.py` SRC, which every publishing round already updates when it publishes -- and
everything else resolves it through `model.build_root()`. `--src` still overrides it everywhere it did before.

Scope. Two deliberate limits, both of which the assertions below state in their own terms:

  * Only round 295 and later. The rounds before that are frozen history: their scripts are not re-run, and the
    scratch, raw and render directories they name were cleaned up many rounds ago. As of Q310 there are 77 such
    dead references (q199-q218); they are recorded in PROJECT_STATE Q310 as a finding, not fixed here, because
    repointing a frozen round's script at a directory that no longer exists would not make it runnable.
  * Only real code. A build directory named in a comment or a docstring is documentation: a past round's record
    keeps its historical path and says the directory is gone. This test reads string literals that would
    actually be evaluated, via the AST for Python and with comments stripped for shell.
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BUILD = REPO / "build"
FLOOR = 295                       # see "Scope" above

# build/q307 and build/q217_cache, but NOT the glob patterns build/q29* / build/q3* that tests/test_q301.py uses
REF = re.compile(r"\bbuild/q(\d+)([A-Za-z0-9_]*)(?![\w*])")


def _tracked(*globs):
    out = subprocess.run(["git", "ls-files", "-z", *globs], cwd=REPO,
                         capture_output=True, text=True, check=True).stdout
    return [REPO / p for p in out.split("\0") if p]


def _docstrings(tree):
    """the id() of every string node that is a module / class / function docstring"""
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            b = getattr(n, "body", None)
            if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant) \
                    and isinstance(b[0].value.value, str):
                out.add(id(b[0].value))
    return out


def _hits(path):
    """[(lineno, 'q307')] for every build dir named in evaluated code of this file, round >= FLOOR"""
    text = path.read_text(encoding="utf-8")
    found = []
    if path.suffix == ".py":
        try:
            tree = ast.parse(text)
        except SyntaxError as e:
            pytest.fail(f"{path.relative_to(REPO)} does not parse: {e}")
        skip = _docstrings(tree)
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in skip:
                found += [(n.lineno, m) for m in REF.finditer(n.value)]
    else:                                     # shell: an unquoted # starts a comment
        for i, line in enumerate(text.splitlines(), 1):
            code = "" if line.lstrip().startswith("#") else line.split("#", 1)[0]
            found += [(i, m) for m in REF.finditer(code)]
    return [(ln, "q" + m.group(1) + m.group(2)) for ln, m in found if int(m.group(1)) >= FLOOR]


def refs():
    rows = []
    for p in _tracked("scripts/*.py", "scripts/**/*.py", "tests/*.py",
                      "scripts/*.sh", "scripts/**/*.sh"):
        if p.name == Path(__file__).name:
            continue
        rows += [(p.relative_to(REPO), ln, d) for ln, d in _hits(p)]
    return rows


def test_every_build_baseline_named_in_code_is_on_disk():
    """The assertion the owner asked for: a hard-coded baseline that is gone is a broken script, and a
    hard-coded baseline that is still there is the next round's broken script."""
    rows = refs()
    assert rows, "the scan found nothing at all -- the file globs or the regex have stopped working"
    missing = [f"{p}:{ln} -> build/{d}" for p, ln, d in rows if not (BUILD / d).is_dir()]
    assert missing == [], (
        f"{len(missing)} of {len(rows)} references name a build directory that is not on disk. A script's or a "
        "test's default must come from scripts/anatomy/q241/model.py build_root(), never from a literal: "
        + "; ".join(missing[:12]))


def test_the_current_baseline_has_exactly_one_home():
    """`model.py` SRC is that one place, and its six page dirs must sit under a single build directory, which is
    what makes `build_root()` well defined."""
    sys.path.insert(0, str(REPO / "scripts/anatomy/q241"))
    import model
    root = model.build_root()
    assert re.fullmatch(r"build/q\d+[A-Za-z0-9_]*", root), f"build_root() returned {root!r}"
    assert (REPO / root).is_dir(), f"model.py SRC points at {root}, which is not on disk"
    for key, d in model.SRC.items():
        assert (REPO / d).is_dir(), f"model.py SRC[{key}] = {d} is not on disk"
        assert d.startswith(root + "/"), f"model.py SRC[{key}] = {d} is not under {root}"


def test_the_deleted_baselines_are_not_named_in_code_anywhere():
    """build/q295 (deleted before Q310), build/q296 and build/q297 (deleted in Q310 with the owner's approval).
    Separate from the test above so that the failure says plainly which round's directory came back."""
    gone = {"q295", "q296", "q297"}
    bad = [f"{p}:{ln} -> build/{d}" for p, ln, d in refs() if d in gone]
    assert bad == [], f"code names a deleted baseline again: {bad}"
