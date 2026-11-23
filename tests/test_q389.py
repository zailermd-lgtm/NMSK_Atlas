"""Q389: the optional display covering ("underwear") -- static checks (the page itself is checked by
scripts/anatomy/q389/verify_cover_q389.py on a regenerated page).

  - the module is in the Z template through its sync script, and only there; it carries the "not anatomy" wording;
  - no private word and no model identifier in the round's files;
  - the build-time maths on a made-up skin slab: the outer sheet is found (not the inner sheet, not the wall), a cut at a
    level keeps exactly the part above it, the taut heights bridge a groove and never go under the least height;
  - the page-side recomputation (viewer/cover/cover.js, run in node) gives the same points as the builder;
  - on the built Base pages, when they are on this machine: briefs on both, a top on the female body only, deterministic,
    every height within its bounds, and with the covering on nothing of the skin it is there to cover can be seen.
"""
import base64, json, re, subprocess, sys, zlib
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q389"))
import make_cover_q389 as mk  # noqa: E402

ZT = REPO / "viewer" / "zan_atlas.template.html"
OT = REPO / "viewer" / "atlas_viewer.template.html"
FILES = [REPO / "viewer/cover/cover.js", REPO / "viewer/cover/cover.css", REPO / "viewer/cover/glue_zan.js", REPO / "scripts/sync_cover_q389.py",
         REPO / "scripts/anatomy/q389/make_cover_q389.py", REPO / "scripts/anatomy/q389/preview_cover_q389.py", REPO / "scripts/anatomy/q389/verify_cover_q389.py"]
PRIVATE = ["ultrasound", "hounsfield", "t1_se", "imaging_tissues", "tissue table", "nmskultrasound", "acoustic", "mrayl", "b-mode"]
PAGES = {"base_m": REPO / "build/q309/viewer_zan_atlas/atlas_viewer_zan_atlas.html", "base_f": REPO / "build/q309/viewer_base_female/atlas_viewer_base_female.html"}


def test_module_is_synced_into_the_z_template_only():
    r = subprocess.run([sys.executable, str(REPO / "scripts/sync_cover_q389.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    z, o = ZT.read_text(encoding="utf-8"), OT.read_text(encoding="utf-8")
    for needle in ("<!-- NMSK-COVER begin -->", "<!-- Q389 html begin -->", "/* COVER glue begin */", "if (coverZ) coverZ.draw();"):
        assert z.count(needle) == 1, needle
    assert '<script type="application/json" id="nmsk-cover">{}</script>' in z      # the template ships it empty; the page's block is made at regen
    assert "NMSKCover" not in o and "nmsk-cover" not in o
    assert z.index("/* POSE glue end */") < z.index("/* COVER glue begin */")     # the glue reads the posed skin


def test_wording_not_anatomy():
    js = (REPO / "viewer/cover/cover.js").read_text(encoding="utf-8")
    assert "A display covering, not an anatomical structure." in js
    assert "hides nothing from measurements" in js
    assert re.search(r"display covering .{1,8} not anatomy", js)
    assert "off by default" in js.lower()


def test_regen_runs_the_builder_for_the_base_pages():
    s = (REPO / "scripts/regen_template_only.py").read_text(encoding="utf-8")
    assert 'scripts/anatomy/q389/make_cover_q389.py", "--inject"' in s
    i = s.index("make_cover_q389.py")
    assert 'if p in ("base_m", "base_f")' in s[i - 400:i]


def test_no_private_words_and_no_model_identifiers():
    rx = re.compile(r"claude|opus|sonnet|haiku|fable|gpt-?\d|gemini", re.I)
    for f in FILES + [Path(__file__)]:
        t = f.read_text(encoding="utf-8")
        low = t.lower()
        if f.name not in ("test_q389.py", "verify_cover_q389.py"):          # these two name the words in order to forbid them
            for w in PRIVATE:
                assert w not in low, (f.name, w)
        if f.name != "test_q389.py":
            assert not rx.search(t), f.name


# ---------------------------------------------------------------- the builder's maths on a made-up slab
def slab(n=12, size=120.0, thick=3.0, groove=True):
    """a closed skin slab: outer sheet at z = bump(x, y) (with a groove along x = 0), inner sheet `thick` under it, a wall around"""
    xs = np.linspace(-size / 2, size / 2, n)
    X, Y = np.meshgrid(xs, xs, indexing="ij")
    Z = np.where(np.abs(X) < size / (n - 1) * 0.6, -8.0, 0.0) if groove else np.zeros_like(X)
    top = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
    bot = top - [0, 0, thick]
    idx = np.arange(n * n).reshape(n, n)
    a, b, c, d = idx[:-1, :-1].ravel(), idx[1:, :-1].ravel(), idx[1:, 1:].ravel(), idx[:-1, 1:].ravel()
    ft = np.concatenate([np.column_stack([a, b, c]), np.column_stack([a, c, d])])          # normal +z
    fb = ft[:, ::-1] + n * n                                                              # normal -z
    ring = np.concatenate([idx[0, :-1], idx[:-1, -1], idx[-1, :0:-1], idx[:0:-1, 0]])
    nxt = np.roll(ring, -1)
    fw = np.concatenate([np.column_stack([ring, ring + n * n, nxt]), np.column_stack([nxt, ring + n * n, nxt + n * n])])
    p, f = np.vstack([top, bot]), np.concatenate([ft, fb, fw])
    # every face points out of the slab: the outer sheet up, the inner sheet down, the wall away from the middle
    nrm = np.cross(p[f[:, 1]] - p[f[:, 0]], p[f[:, 2]] - p[f[:, 0]])
    cen = p[f].mean(1)
    want = np.zeros_like(nrm); want[:len(ft), 2] = 1; want[len(ft):2 * len(ft), 2] = -1; want[2 * len(ft):, :2] = cen[2 * len(ft):, :2]
    flip = (nrm * want).sum(1) < 0
    f[flip] = f[flip][:, ::-1]
    return p, f, len(ft)


def inner_cloud(size=120.0):
    from scipy.spatial import cKDTree
    g = np.linspace(-size / 2, size / 2, 25)
    X, Y = np.meshgrid(g, g, indexing="ij")
    return cKDTree(np.column_stack([X.ravel(), Y.ravel(), np.full(X.size, -25.0)]))


def test_outer_sheet_of_a_slab():
    p, f, nt = slab()
    out, _ = mk.outer_faces(p, f, inner_cloud())
    assert out[:nt].all(), "every face of the outer sheet"
    assert not out[nt:].any(), "no face of the inner sheet or of the wall"


def test_cut_keeps_the_part_above_the_level():
    class S:      # the smallest thing clip() needs
        pos = np.array([[0, 0, 0], [10, 0, 0], [0, 10, 0]], float)
        tri = np.array([[0, 1, 2]])
    fv = S.pos[:, 0]                                                    # the field is x
    kept = mk.clip(S, [(0, np.eye(3))], fv, 4.0, True)
    area = lambda W: 0.5 * abs(np.cross((W @ S.pos)[1] - (W @ S.pos)[0], (W @ S.pos)[2] - (W @ S.pos)[0])[2])
    assert all(((W @ S.pos)[:, 0] >= 4 - 1e-9).all() for _, W in kept)
    assert abs(sum(area(W) for _, W in kept) - 0.5 * 6 * 6) < 1e-9       # the corner triangle beyond x = 4
    low = mk.clip(S, [(0, np.eye(3))], fv, 4.0, False)
    assert abs(sum(area(W) for _, W in low) + sum(area(W) for _, W in kept) - 50) < 1e-9


def test_taut_heights_bridge_a_groove_and_keep_the_least_height():
    p, f, nt = slab()
    top, tri = p[:144], f[:nt]
    nrm = mk.vertex_normals(top, tri)
    h = mk.relax(top, nrm, tri, mk.H0, mk.HMAX)
    assert h.min() >= mk.H0 - 1e-9 and h.max() <= mk.HMAX + 1e-9
    groove = np.abs(top[:, 0]) < 6
    inner = groove & (np.abs(top[:, 1]) < 40)
    assert h[inner].min() > mk.H0 + 3.0, "the groove is bridged"
    assert np.allclose(h[~groove & (np.abs(top[:, 0]) > 30)], mk.H0, atol=0.3), "flat skin keeps the least height"


def test_page_side_recomputation_matches(tmp_path):
    rng = np.random.default_rng(3)
    pos = rng.normal(size=(40, 3)) * 30
    nrm = rng.normal(size=(40, 3)); nrm /= np.linalg.norm(nrm, axis=1)[:, None]
    nb = 60
    abc = rng.integers(0, 40, size=(nb, 3))
    w = rng.dirichlet([1, 1, 1], size=nb)
    wq = np.round(w * 65535)
    h = np.round(rng.uniform(2.5, 16, nb) * 100)
    bind = np.column_stack([np.zeros(nb), abc, wq[:, :2], h]).astype(np.uint16)
    wa, wb = bind[:, 4] / 65535, bind[:, 5] / 65535
    wc = 1 - wa - wb
    P = pos[abc[:, 0]] * wa[:, None] + pos[abc[:, 1]] * wb[:, None] + pos[abc[:, 2]] * wc[:, None]
    N = nrm[abc[:, 0]] * wa[:, None] + nrm[abc[:, 1]] * wb[:, None] + nrm[abc[:, 2]] * wc[:, None]
    N /= np.linalg.norm(N, axis=1)[:, None]
    want = P + N * (bind[:, 6] / 100)[:, None]
    js = """
const C = require(%s);
const d = JSON.parse(require('fs').readFileSync(%s, 'utf8'));
const g = {nb: d.nb, nf: 1, bind: new Uint16Array(d.bind), fix: new Float32Array([1, 2, 3, 0, 1, 0])};
g.pos = new Float32Array(3 * (g.nb + 1)); g.nrm = new Float32Array(3 * (g.nb + 1));
C.compute(g, () => ({pos: new Float32Array(d.pos), nrm: new Float32Array(d.nrm)}));
console.log(JSON.stringify(Array.from(g.pos)));
""" % (json.dumps(str(REPO / "viewer/cover/cover.js")), json.dumps(str(tmp_path / "in.json")))
    (tmp_path / "in.json").write_text(json.dumps({"nb": nb, "bind": bind.ravel().tolist(), "pos": pos.ravel().tolist(), "nrm": nrm.ravel().tolist()}))
    (tmp_path / "run.js").write_text(js)
    r = subprocess.run(["node", str(tmp_path / "run.js")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    got = np.array(json.loads(r.stdout)).reshape(-1, 3)
    assert np.abs(got[:nb] - want).max() < 2e-3
    assert np.allclose(got[nb], [1, 2, 3])


# ---------------------------------------------------------------- the built pages (skipped where build/ is not on this machine)
def unpack(o):
    f = lambda k, t: np.frombuffer(zlib.decompress(base64.b64decode(o[k])), dtype=t) if o.get(k) else np.zeros(0, t)
    return f("bind", "<u2").reshape(-1, 7), f("fix", "<f4").reshape(-1, 6), f("body", "<u2").reshape(-1, 3), f("rim", "<u2").reshape(-1, 3)


@pytest.mark.parametrize("page", ["base_m", "base_f"])
def test_built_page(page):
    html = PAGES[page]
    if not html.exists():
        pytest.skip("build/q309 is not on this machine")
    ctx, gs, doc = mk.build(html)
    assert list(gs) == (["briefs", "top"] if page == "base_f" else ["briefs"])
    assert mk.block(doc) == mk.block(mk.build(html)[2]), "the same geometry gives the same block"
    assert "not an anatomical structure" in doc["what"] and "hides nothing from measurements" in doc["what"]
    M = ctx["M"]
    for i, sid, vc in doc["src"]:
        assert M[i]["id"] == sid and M[i]["vc"] == vc and M[i]["sys"] == "skin"
        assert not mk.LIMB.search(M[i]["name"])
    for key, o in doc["garments"].items():
        bind, fix, body, rim = unpack(o)
        nf = o["nf"]
        n = len(bind) + nf
        assert len(bind) == o["nb"] and len(fix) == nf and n < 65536
        assert body.max() < n and rim.max() < n
        assert (bind[:, 0] < len(doc["src"])).all()
        for q in range(3):
            assert (bind[:, 1 + q] < np.array([doc["src"][k][2] for k in bind[:, 0]])).all()
        assert (bind[:, 4].astype(int) + bind[:, 5] <= 65536).all()
        if key == "briefs":
            assert nf > 100 and np.allclose(np.linalg.norm(fix[:, 3:], axis=1), 1, atol=1e-3)
            assert any(mk.GENITAL.search(M[doc["src"][k][0]]["name"]) for k in set(bind[:, 0].tolist())), "the shell covers the genital skin too, under the pouch"
        h = bind[:, 6] / 100
        edge = h < 1.0                                               # the wall's foot on the skin
        assert np.allclose(h[edge], 0.2) and h[~edge].min() >= mk.H0 - 0.01 and h.max() <= mk.HMAX + 0.01
        st = doc["stats"][key]
        assert st["holes"] <= 260, st
    assert len(mk.block(doc)) < 600_000
    # nothing it is there to cover can be seen with it on
    import preview_cover_q389 as pv
    cov = pv.coverage(html, scale=0.5)
    for key, views in cov.items():
        for view, (seen, bare) in views.items():
            assert seen <= max(2, 0.01 * bare), (key, view, seen, bare)
