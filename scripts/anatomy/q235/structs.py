"""Q235: the CVH structures that are brought onto the female pages, as oriented closed solids in the CVH atlas-axis frame (before registration), with the repair record.
Source meshes: third_party/cvh_wu2015/meshes (Wu et al. 2015 PLOS ONE S3 Fig, CC BY 4.0). Triangle winding is made consistent (vertex order only; no vertex moves), components below FRAGMENT_FACES triangles are dropped
(and listed), a paired structure is split into its left / right component by the sign of x - 184 after the page registration."""
from __future__ import annotations
import numpy as np, trimesh
from scripts.anatomy.q235 import cvh, solid

FRAGMENT_FACES = 100
# key: (cvh index, display name, latin, cat, folder, region, paired)
S = {
    "clitoris_cavernous_body": (39, "Cavernous body of the clitoris (both crura and body, CVH)", "Corpus cavernosum clitoridis", "organ", "viscera", "pelvis", False),
    "vestibular_bulb": (38, "Vestibular bulb (CVH)", "Bulbus vestibuli", "organ", "viscera", "pelvis", True),
    "bartholin_gland": (22, "Greater vestibular gland (Bartholin, CVH)", "Glandula vestibularis major", "organ", "viscera", "pelvis", True),
    "bulbospongiosus_cvh": (37, "Bulbospongiosus (CVH, both sides joined)", "Musculus bulbospongiosus", "muscle", "trunk", "trunk", False),
    "ischiocavernosus_cvh": (36, "Ischiocavernosus (CVH)", "Musculus ischiocavernosus", "muscle", "trunk", "trunk", True),
    "superficial_transverse_perineal_cvh": (26, "Superficial transverse perineal muscle (CVH)", "Musculus transversus perinei superficialis", "muscle", "trunk", "trunk", False),
    "deep_perineal_muscle_cvh": (25, "Deep transverse perineal muscle (CVH)", "Musculus transversus perinei profundus", "muscle", "trunk", "trunk", False),
    "urethral_sphincter_cvh": (31, "External urethral sphincter proper (CVH)", "Musculus sphincter urethrae externus", "muscle", "trunk", "trunk", False),
    "urethral_sphincter_raphe_cvh": (32, "Raphe of the urethral sphincter (CVH)", "Raphe sphincteris urethrae", "muscle", "trunk", "trunk", False),
    "urethral_compressor_cvh": (33, "Compressor urethrae (CVH)", "Musculus compressor urethrae", "muscle", "trunk", "trunk", False),
    "urethrovaginal_sphincter_cvh": (34, "Urethrovaginal sphincter (CVH)", "Musculus sphincter urethrovaginalis", "muscle", "trunk", "trunk", False),
    "urethra_female_submucous_layer": (35, "Female urethra, submucous layer (CVH)", "Tela submucosa urethrae femininae", "organ", "viscera", "pelvis", False),
    "perineal_body": (24, "Perineal body (CVH)", "Corpus perineale", "organ", "viscera", "pelvis", False),
}


def mc_volume_cm3(V, F, n=60000, seed=0):
    """independent volume check: ray-parity inside test of uniform random points in the bounding box (does not use the triangle orientation) -> (volume, standard error), cm3"""
    rng = np.random.default_rng(seed)
    m = trimesh.Trimesh(V, F, process=False)
    lo, hi = V.min(0), V.max(0)
    P = lo + rng.random((n, 3)) * (hi - lo)
    f = float(m.contains(P).mean()); box = float(np.prod(hi - lo)) / 1000.0
    return round(f * box, 4), round(float(np.sqrt(f * (1 - f) / n)) * box, 4)


def build(key, sx):
    """-> list of dict(V, F, side_x, info) one per kept component, in the CVH atlas-axis frame (file frame mapped with sx), triangles oriented outward"""
    idx = S[key][0]
    V0, F0 = cvh.load_raw(idx)
    comps = solid.components(V0, F0)
    out, dropped = [], []
    for v, f in sorted(comps, key=lambda c: -len(c[1])):
        if len(f) < FRAGMENT_FACES:
            dropped.append(dict(faces=int(len(f)), area_mm2=round(float(trimesh.Trimesh(v, f, process=False).area), 2)))
            continue
        f2 = solid.orient_bfs(v, f)
        W, G = cvh.to_atlas(v, sx, f2)
        nb, nn = solid.edge_stats(f)
        sv = solid.signed_volume_cm3(W, G)
        m = trimesh.Trimesh(W, G, process=False)
        closed_manifold = (nb == 0 and nn == 0)
        mc = mc_volume_cm3(W, G)
        out.append(dict(V=W, F=G, x_mid=float(np.mean(W[:, 0])), info=dict(volume_montecarlo_cm3=mc[0], volume_montecarlo_se_cm3=mc[1],
            cvh_index=idx, faces=int(len(G)), vertices=int(len(W)), open_edges=nb, nonmanifold_edges=nn, closed=bool(nb == 0), edge_manifold=closed_manifold,
            winding_was_consistent=bool(trimesh.Trimesh(v, f, process=False).is_winding_consistent), volume_cvh_cm3=round(sv, 4), area_cvh_cm2=round(float(m.area) / 100, 3),
            euler=int(m.euler_number))))
    for o in out:
        o["info"]["dropped_fragments"] = dropped
    return out


LUMEN_AREA_CUT_MM2 = 10.0
S["urethra_female_lumen"] = (30, "Female urethra, lumen (CVH; urethral part of the bladder + urethra lumen, capped)", "Lumen urethrae femininae", "organ", "viscera", "pelvis", False)


def urethral_lumen(sx):
    """CVH 'Bladder and urethral lumen' (closed, one component, 13,640 triangles) cut by the plane perpendicular to the urethral axis (first principal axis of the CVH submucous layer of the urethra, pointing inferior) at the most
    superior position where the lumen cross-section is below LUMEN_AREA_CUT_MM2 (the bladder neck: 114 mm2 at 1 mm above, 9.7 mm2 at the plane); the part distal to the plane (the urethral lumen, a collapsed channel of about 1 mm2
    cross-section) is kept and the planar cut is closed by a flat cap (honest closing of the single boundary loop; its area is recorded). -> list with one dict like build()"""
    V, F = cvh.load_raw(30)
    F = solid.orient_bfs(V, F)
    V35, _ = cvh.load_raw(35)
    c = V35.mean(0)
    ax = np.linalg.svd(V35 - c)[2][0]
    ax = ax if ax[2] > 0 else -ax                       # file z increases inferior
    m = trimesh.Trimesh(V, F, process=False)
    t_cut = None
    for t0 in np.arange(-30.0, 0.0, 0.25):
        sec = m.section(plane_origin=c + ax * t0, plane_normal=ax)
        a = 0.0 if sec is None else sum(p.area for p in sec.to_2D()[0].polygons_full)
        if t_cut is None and t0 > -20 and a < LUMEN_AREA_CUT_MM2:
            t_cut = float(t0); a_cut = float(a)
    assert t_cut is not None
    part = trimesh.intersections.slice_mesh_plane(m, plane_normal=ax, plane_origin=c + ax * t_cut, cap=True)
    cap_area = 0.0
    sec = m.section(plane_origin=c + ax * t_cut, plane_normal=ax)
    cap_area = sum(p.area for p in sec.to_2D()[0].polygons_full)
    Vp, Fp = np.asarray(part.vertices), np.asarray(part.faces)
    Fp = solid.orient_bfs(Vp, Fp)
    W, G = cvh.to_atlas(Vp, sx, Fp)
    mm = trimesh.Trimesh(W, G, process=False)
    t_end = float(((Vp - c) @ ax).max())
    meatus_file = Vp[((Vp - c) @ ax) > t_end - 1.5].mean(0)
    mcv = mc_volume_cm3(W, G, 150000)
    info = dict(volume_montecarlo_cm3=mcv[0], volume_montecarlo_se_cm3=mcv[1], cvh_index=30, faces=int(len(G)), vertices=int(len(W)), closed=bool(mm.is_watertight), edge_manifold=bool(mm.is_watertight), winding_was_consistent=False,
                volume_cvh_cm3=round(float(mm.volume) / 1000, 5), area_cvh_cm2=round(float(mm.area) / 100, 3), euler=int(mm.euler_number), dropped_fragments=[],
                cut_plane=dict(axis_file=ax.round(4).tolist(), origin_file_mm=(c + ax * t_cut).round(2).tolist(), t_mm=t_cut, lumen_cross_section_mm2=round(a_cut, 2), cap_area_mm2=round(float(cap_area), 2), lumen_length_mm=round(t_end - t_cut, 1)),
                meatus_file_mm=meatus_file.round(2).tolist(), capped=True)
    return [dict(V=W, F=G, x_mid=float(W[:, 0].mean()), info=info, meatus=cvh.to_atlas(meatus_file[None], sx)[0])]
