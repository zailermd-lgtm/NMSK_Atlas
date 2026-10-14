"""Q234: the HuBMAP HRA 3D Reference Object Library objects of the Visible Human FEMALE (CC BY 4.0) that Q233 did not use: vagina (v1.2), ligaments of the uterus and ovaries (v1.2), both mammary glands (v1.3),
plus the thoracic vertebrae (v1.2) as the registration anchor of the thorax. Builds the decimated meshes in the HRA frame (atlas axis convention, mm) once and caches them in data/derived/Q234_hra_meshes.npz
so the page scripts need no download. Sources (raw.githubusercontent.com/hubmapconsortium/ccf-3d-reference-object-library/<commit>/VH_Female/...) and their sha256 are in third_party/hra_vh_f/SOURCES_Q234.json.
    python3 scripts/anatomy/q234/hra_q234.py            # fetch (if needed) + build the npz + data/derived/Q234_hra_meshes.json (volumes, decimation errors)"""
from __future__ import annotations
import hashlib, json, sys, urllib.request
from pathlib import Path
import numpy as np, trimesh
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.anatomy.q233 import hra_register as H  # noqa: E402

TP = REPO / "third_party" / "hra_vh_f"
DL = TP / "_download"
NPZ = REPO / "data" / "derived" / "Q234_hra_meshes.npz"
INFO = REPO / "data" / "derived" / "Q234_hra_meshes.json"
COMMIT = "f1a3a63f110e27ff0736047d52d04dba5d3087f9"        # hubmapconsortium/ccf-3d-reference-object-library main at the time of the download (2026-10-14)
RAW = f"https://raw.githubusercontent.com/hubmapconsortium/ccf-3d-reference-object-library/{COMMIT}/VH_Female/"
FILES = {  # local name -> (path in the library, sha256)
    "v1.2_VH_F_Vagina": ("v1.2/VH_F_Vagina.glb", "ef334a9315ce0dd7e112bd757d22dce4bf57722c7fd0cac81a05d86209bfce34"),
    "v1.2_VH_F_Ligaments_Uterus_Ovaries": ("v1.2/VH_F_Ligaments_Uterus_Ovaries.glb", "ba7bd64c8c40cca6c12d944be4aa7cecd6ecc1fa577be3000337ce114f44f846"),
    "v1.3_VH_F_mammary_gland_L": ("v1.3/VH_F_mammary_gland_L.glb", "5181797d8b669580d0243684ce10e61657881178c9bd56b4ba338547ecb1099e"),
    "v1.3_VH_F_mammary_gland_R": ("v1.3/VH_F_mammary_gland_R.glb", "7fb6c2dd90190a80dbcca487e3aaa27cc801d1c66a205840ea36a6c851082ff0"),
    "v1.2_VH_F_Vertebrae": ("v1.2/VH_F_Vertebrae.glb", "bdbea49a40e9e64cac1c8f0d67b6483686a3cc9617f7cae645e58159e4b02984"),
}


def fetch(name):
    """path of the GLB (repo copy, else the download dir; downloaded and sha256-checked on first use)"""
    for d in (TP, DL):
        p = d / f"{name}.glb"
        if p.exists():
            return p
    rel, sha = FILES[name]
    DL.mkdir(parents=True, exist_ok=True)
    p = DL / f"{name}.glb"
    with urllib.request.urlopen(RAW + rel, timeout=300) as r:
        data = r.read()
    if hashlib.sha256(data).hexdigest() != sha:
        raise RuntimeError(f"sha256 mismatch for {rel}")
    p.write_bytes(data)
    return p


def parts_of(name):
    H.HRA = fetch(name).parent
    return {n: (v, f) for n, v, f in H.hra_mesh(name)}


def decimate(v, f, n):
    import fast_simplification as fs
    if len(f) <= n:
        return np.asarray(v, float), np.asarray(f)
    v2, f2 = fs.simplify(np.asarray(v, np.float32), np.asarray(f, np.int32), target_count=n, agg=5)
    return np.asarray(v2, float), np.asarray(f2)


def merged(parts):
    """concatenate surfaces (vertex merge inside each, degenerate / duplicate faces dropped)"""
    V, F, off = [], [], 0
    for v, f in parts:
        m = trimesh.Trimesh(v, f, process=True)
        m.update_faces(m.nondegenerate_faces()); m.remove_unreferenced_vertices()
        V.append(np.asarray(m.vertices)); F.append(np.asarray(m.faces) + off); off += len(m.vertices)
    return np.vstack(V), np.vstack(F)


def dev(v, f, v0, f0, n=20000):
    """symmetric surface deviation (median, p95, max mm) between two meshes"""
    a = trimesh.Trimesh(v, f, process=False).sample(n); b = trimesh.Trimesh(v0, f0, process=False).sample(n)
    d1 = cKDTree(b).query(a)[0]; d2 = cKDTree(a).query(b)[0]
    d = np.concatenate([d1, d2])
    return dict(median=round(float(np.median(d)), 2), p95=round(float(np.quantile(d, .95)), 2), max=round(float(d.max()), 2))


# id, display name, Terminologia name, cat, folder, region, side, hra file, [part-name substrings or None], mode ("closed": voxel envelope; "surface": the HRA surface as is, decimated), pitch, closing, triangles
LIG = "v1.2_VH_F_Ligaments_Uterus_Ovaries"
GL = "v1.3_VH_F_mammary_gland_{}"
STRUCTS = [
    ("vagina", "Vagina", "Vagina", "organ", "viscera", "pelvis", None, "v1.2_VH_F_Vagina", ["VH_F_vagina", "VH_F_cervicovaginal_junction"], "closed", 0.5, 1, 6000),
    ("round_ligament_uterus_l", "Round ligament of the uterus (left)", "Ligamentum teres uteri sinistrum", "ligament", "ligaments", "pelvis", "left", LIG, ["left_round_ligament"], "surface", 0, 0, 1100),
    ("round_ligament_uterus_r", "Round ligament of the uterus (right)", "Ligamentum teres uteri dextrum", "ligament", "ligaments", "pelvis", "right", LIG, ["right_round_ligament"], "surface", 0, 0, 1100),
    ("uterosacral_ligament_l", "Uterosacral ligament (left)", "Ligamentum sacrouterinum sinistrum", "ligament", "ligaments", "pelvis", "left", LIG, ["left_uterosacral"], "surface", 0, 0, 2000),
    ("uterosacral_ligament_r", "Uterosacral ligament (right)", "Ligamentum sacrouterinum dextrum", "ligament", "ligaments", "pelvis", "right", LIG, ["right_uterosacral"], "surface", 0, 0, 2000),
    ("cardinal_ligament_uterus_l", "Cardinal ligament of the uterus (left)", "Ligamentum cardinale sinistrum", "ligament", "ligaments", "pelvis", "left", LIG, ["left_cardinal"], "surface", 0, 0, 3000),
    ("cardinal_ligament_uterus_r", "Cardinal ligament of the uterus (right)", "Ligamentum cardinale dextrum", "ligament", "ligaments", "pelvis", "right", LIG, ["right_cardinal"], "surface", 0, 0, 3000),
    ("broad_ligament_uterus", "Broad ligament of the uterus", "Ligamentum latum uteri", "ligament", "ligaments", "pelvis", None, LIG, ["VH_F_broad_ligament"], "surface", 0, 0, 7000),
    ("ovarian_ligament_l", "Ligament of the ovary (left)", "Ligamentum ovarii proprium sinistrum", "ligament", "ligaments", "pelvis", "left", LIG, ["ovarian_ligament_L"], "surface", 0, 0, 200),
    ("ovarian_ligament_r", "Ligament of the ovary (right)", "Ligamentum ovarii proprium dextrum", "ligament", "ligaments", "pelvis", "right", LIG, ["ovarian_ligament_R"], "surface", 0, 0, 200),
    ("suspensory_ligament_ovary_l", "Suspensory ligament of the ovary (left)", "Ligamentum suspensorium ovarii sinistrum", "ligament", "ligaments", "pelvis", "left", LIG, ["suspensory_ligament_of_ovary_L"], "surface", 0, 0, 1300),
    ("suspensory_ligament_ovary_r", "Suspensory ligament of the ovary (right)", "Ligamentum suspensorium ovarii dextrum", "ligament", "ligaments", "pelvis", "right", LIG, ["suspensory_ligament_of_ovary_R"], "surface", 0, 0, 900),
    ("mesosalpinx_l", "Mesosalpinx (left)", "Mesosalpinx sinistra", "ligament", "ligaments", "pelvis", "left", LIG, ["mesosalpinx_L"], "surface", 0, 0, 1900),
    ("mesosalpinx_r", "Mesosalpinx (right)", "Mesosalpinx dextra", "ligament", "ligaments", "pelvis", "right", LIG, ["mesosalpinx_R"], "surface", 0, 0, 1800),
    ("mesovarium_l", "Mesovarium (left)", "Mesovarium sinistrum", "ligament", "ligaments", "pelvis", "left", LIG, ["mesovarium_L"], "surface", 0, 0, 650),
    ("mesovarium_r", "Mesovarium (right)", "Mesovarium dextrum", "ligament", "ligaments", "pelvis", "right", LIG, ["mesovarium_R"], "surface", 0, 0, 190),
]
for S_, L_, side, lat in (("l", "L", "left", "sinistra"), ("r", "R", "right", "dextra")):
    g = GL.format(L_)
    STRUCTS += [
        (f"breast_fat_{S_}", f"Breast: fat pad ({side})", f"Corpus adiposum mammae {lat}", "organ", "viscera", "breast", side, g, ["_fat_"], "closed", 0.8, 2, 7000),
        (f"mammary_gland_{S_}", f"Mammary gland: lobes ({side})", f"Lobi glandulae mammariae {lat}", "organ", "viscera", "breast", side, g, ["mammary_lobes"], "surface", 0, 0, 9000),
        (f"lactiferous_ducts_{S_}", f"Lactiferous ducts and sinuses ({side})", f"Ductus et sinus lactiferi {lat}", "organ", "viscera", "breast", side, g, ["lactiferous_ducts", "lactiferous_sinuses"], "surface", 0, 0, 6500),
        (f"areola_{S_}", f"Areola ({side})", f"Areola mammae {lat}", "organ", "viscera", "breast", side, g, ["areola_", "areolar_tubercles"], "closed", 0.4, 1, 1500),
        (f"nipple_{S_}", f"Nipple ({side})", f"Papilla mammaria {lat}", "organ", "viscera", "breast", side, g, ["nipple"], "closed", 0.3, 1, 900),
        (f"breast_suspensory_ligaments_{S_}", f"Suspensory ligaments of the breast ({side})", f"Ligamenta suspensoria mammaria {lat}", "ligament", "ligaments", "breast", side, g, ["suspensory_ligaments"], "surface", 0, 0, 5000),
    ]


def build():
    out, info = {}, {}
    cache = {}
    for sid, name, latin, cat, folder, region, side, obj, keys, mode, pitch, clo, ntri in STRUCTS:
        P = cache.setdefault(obj, parts_of(obj))
        sel = [(n, vf) for n, vf in P.items() if any(k in n for k in keys)]
        assert sel, (sid, keys, list(P))
        if mode == "closed":
            V, F, inf = H.closed_surface([(n, v, f) for n, (v, f) in sel], pitch=pitch, close_it=clo)
            V0, F0 = V, F
            for k_ in (1.0, 1.04, 0.96, 1.08, 0.92, 1.12):                  # a closed envelope must stay one closed manifold after decimation (volume in the table)
                V, F = decimate(V0, F0, int(ntri * k_))
                m = trimesh.Trimesh(V, F, process=True); trimesh.repair.fix_normals(m)
                cc = m.split(only_watertight=False)
                if len(cc) > 1:
                    m = max(cc, key=lambda c: len(c.faces)); m.remove_unreferenced_vertices()
                if m.is_watertight:
                    break
            V, F = np.asarray(m.vertices), np.asarray(m.faces)
            rec = dict(mode="closed envelope", voxel_pitch_mm=pitch, closing=clo, triangles_full=int(len(F0)), triangles=int(len(F)), watertight=bool(m.is_watertight), volume_cm3=round(abs(m.volume) / 1000, 2),
                       envelope_to_source_p95_mm=inf["closed_surface_to_source_mm"]["p95"], decimation_deviation_mm=dev(V, F, V0, F0))
        else:
            V0, F0 = merged([vf for n, vf in sel])
            V, F = decimate(V0, F0, ntri)
            m = trimesh.Trimesh(V, F, process=True)
            m.update_faces(m.nondegenerate_faces()); m.remove_unreferenced_vertices()
            V, F = np.asarray(m.vertices), np.asarray(m.faces)
            m0 = trimesh.Trimesh(V0, F0, process=False)
            rec = dict(mode="HRA surface as is", triangles_full=int(len(F0)), triangles=int(len(F)), watertight=bool(m.is_watertight), volume_cm3=round(abs(m.volume) / 1000, 3) if m.is_watertight else None,
                       area_cm2=round(float(m.area) / 100, 2), area_full_cm2=round(float(m0.area) / 100, 2), decimation_deviation_mm=dev(V, F, V0, F0), parts=[n for n, _ in sel])
        out[sid + "_v"] = np.asarray(V, np.float32); out[sid + "_f"] = np.asarray(F, np.int32)
        info[sid] = dict(name=name, latin=latin, cat=cat, folder=folder, region=region, side=side, hra_file=obj, **rec)
        print(sid, rec["triangles"], rec.get("volume_cm3"), rec["decimation_deviation_mm"], flush=True)
    # thoracic registration anchor: the HRA thoracic vertebrae (surface samples)
    np.random.seed(0)
    P = parts_of("v1.2_VH_F_Vertebrae")
    pts = np.vstack([trimesh.Trimesh(v, f, process=False).sample(max(500, len(f) // 3)) for n, (v, f) in P.items() if "thoracic" in n])
    out["anchor_thoracic_vertebrae"] = pts.astype(np.float32)
    # lung / heart-free: nipple tip and apex references
    np.savez_compressed(NPZ, **out)
    INFO.write_text(json.dumps(dict(commit=COMMIT, source=RAW, files={k: dict(path=v[0], sha256=v[1]) for k, v in FILES.items()}, structures=info), indent=1) + "\n")
    return info


def load():
    """{id: (V, F)} in the HRA frame (atlas axis convention, mm) + the thoracic anchor points + the structure table"""
    if not NPZ.exists():
        build()
    z = np.load(NPZ)
    info = json.loads(INFO.read_text())["structures"]
    return {sid: (z[sid + "_v"].astype(float), z[sid + "_f"]) for sid in info}, z["anchor_thoracic_vertebrae"].astype(float), info


if __name__ == "__main__":
    build()
