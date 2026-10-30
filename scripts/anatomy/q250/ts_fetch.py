#!/usr/bin/env python3
"""Q250: fetch ONLY the skeleton segmentation masks of selected adult women from the TotalSegmentator dataset v2.0.1 (Zenodo record 10047292, CC BY 4.0; Wasserthal J et al.,
Radiology: Artificial Intelligence 2023;5(5):e230024, doi 10.1148/ryai.230024) by HTTP range requests into the 23.6 GB zip (central directory 14 MB, then one ~1 MB range per case).
No CT image is downloaded.   python3 scripts/anatomy/q250/ts_fetch.py OUT_DIR [--max-age 70]
Selection (meta.csv inside the zip): gender f, age 20-70, study type contains pelvis / whole body / polytrauma, pathology not trauma / tumour, pathology location not pelvis / bones / extremity.
Writes OUT_DIR/<case>/<label>.nii.gz for hip_*, sacrum, femur_*, vertebrae_*, rib_*, sternum, clavicula_*, scapula_*, humerus_*, skull, costal_cartilages and OUT_DIR/selection.json."""
import csv, io, json, os, struct, subprocess, sys, time, zlib
from concurrent.futures import ThreadPoolExecutor

URL = "https://zenodo.org/api/records/10047292/files/Totalsegmentator_dataset_v201.zip/content"
SIZE = 23581218285
KEEP = ("hip_", "sacrum", "femur_", "vertebrae_", "rib_", "sternum", "clavicula_", "scapula_", "humerus_", "skull", "costal")


def rng(a, b):
    for k in range(5):
        try:
            return subprocess.run(["curl", "-sS", "-m", "600", "-L", "-r", f"{a}-{b}", URL], capture_output=True, check=True).stdout
        except Exception:  # noqa: BLE001
            time.sleep(3 + 3 * k)
    raise RuntimeError("range request failed")


def central_directory():
    tail = rng(SIZE - 70000, SIZE - 1)
    k = tail.rfind(b"PK\x06\x06")
    _, _, _, _, _, _, n, _, cd_size, cd_off = struct.unpack("<IQHHIIQQQQ", tail[k:k + 56])
    d = rng(cd_off, cd_off + cd_size - 1)
    pos, ents = 0, []
    while pos < len(d) and d[pos:pos + 4] == b"PK\x01\x02":
        (_, _, _, _, comp, _, _, _, csz, usz, nl, el, cl, _, _, _, off) = struct.unpack("<IHHHHHHIIIHHHHHII", d[pos:pos + 46])
        name = d[pos + 46:pos + 46 + nl].decode(); extra = d[pos + 46 + nl:pos + 46 + nl + el]
        if 0xFFFFFFFF in (usz, csz, off):
            p = 0
            while p < len(extra):
                hid, sz = struct.unpack("<HH", extra[p:p + 4])
                if hid == 1:
                    q = p + 4
                    if usz == 0xFFFFFFFF: usz = struct.unpack("<Q", extra[q:q + 8])[0]; q += 8
                    if csz == 0xFFFFFFFF: csz = struct.unpack("<Q", extra[q:q + 8])[0]; q += 8
                    if off == 0xFFFFFFFF: off = struct.unpack("<Q", extra[q:q + 8])[0]; q += 8
                p += 4 + sz
        ents.append((name, comp, csz, usz, off)); pos += 46 + nl + el + cl
    return ents


def member(ent):
    name, comp, csz, usz, off = ent
    h = rng(off, off + 30 + 400)
    nl, el = struct.unpack("<HH", h[26:30]); s = off + 30 + nl + el
    raw = rng(s, s + csz - 1)
    return raw if comp == 0 else zlib.decompress(raw, -15)


def main(out, max_age=70):
    os.makedirs(out, exist_ok=True)
    ents = central_directory(); by = {}
    for e in ents:
        p = e[0].split("/")
        if len(p) == 3 and p[1] == "segmentations" and p[2]:
            by.setdefault(p[0], []).append(e)
    meta = next(e for e in ents if e[0] == "meta.csv")
    rows = list(csv.DictReader(io.StringIO(member(meta).decode("utf-8-sig")), delimiter=";"))
    sel = []
    for x in rows:
        if x["gender"] != "f" or not x["age"] or not (20 <= float(x["age"]) <= max_age): continue
        if not any(k in x["study_type"] for k in ("pelvis", "whole body", "polytrauma")): continue
        if x["pathology"] in ("trauma", "tumor") or any(k in x["pathology_location"] for k in ("pelvis", "bones", "extremity")): continue
        sel.append(x)
    json.dump(sel, open(os.path.join(out, "selection.json"), "w"), indent=1)

    def job(x):
        cid = x["image_id"]; l = by[cid]; lo = min(e[4] for e in l); hi = max(e[4] + e[2] for e in l) + 400
        d = os.path.join(out, cid); os.makedirs(d, exist_ok=True)
        if os.path.exists(os.path.join(d, ".done")): return
        raw = rng(lo, hi)
        for name, comp, csz, usz, off in l:
            o = off - lo; nl, el = struct.unpack("<HH", raw[o + 26:o + 30]); s = o + 30 + nl + el
            b = raw[s:s + csz]; b = b if comp == 0 else zlib.decompress(b, -15)
            nm = name.split("/")[-1]
            if nm.startswith(KEEP): open(os.path.join(d, nm), "wb").write(b)
        open(os.path.join(d, ".done"), "w").write("1")
    with ThreadPoolExecutor(3) as ex: list(ex.map(job, sel))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[sys.argv.index("--max-age") + 1]) if "--max-age" in sys.argv else 70)
