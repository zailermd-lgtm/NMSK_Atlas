#!/usr/bin/env python3
"""Q383 (owner 7) -- the simulated scan image against the documented appearance, measured on six fixed views.

    python3 scripts/anatomy/q383/verify_image_q383.py PAGE_DIR [--shots DIR] [--tag after] [--report-only]

The views are seated from the page's own meshes (a muscle's centroid, the bone under it): anterior thigh transverse and
longitudinal, posterior calf transverse, volar forearm transverse, carpal tunnel transverse, supraspinatus long axis; linear
probe, the frame the page itself computes (NMSKUltrasound.frameNow, 480-px tier). Every interface is taken from the frame's own
label / structure rasters (scripts/anatomy/q383/image_metrics_q383.py), then looked for in the image:
  1  a bright line within 3 px of every muscle | muscle mesh boundary that lies within ~35 deg of square to the beam (epimysium /
     septum: before Q383 no echo at all), of every muscle / nerve / vessel sheath and of every fascia mesh
  2  brightness order: fat < fascia line, muscle < fascia line; bone: cortex line >= muscle + 20 dB, 3-8 mm below it <= muscle - 25 dB
  3  like tissue reads alike with depth (muscle, upper against lower half of its depth range, within 6 dB)
  4  muscle architecture: along the fibres (thigh longitudinal) the bright marks run on as lines, across them (transverse views) they do not
  5  the beam is an array's (lateral width at 5 mm depth <= 1 mm; it was 8 mm), frame time reported for the 480 and the live 320 tier
--report-only prints the numbers without judging (for the page before the change). Prints Q383_IMAGE_OK / Q383_IMAGE_FAIL."""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import image_metrics_q383 as M  # noqa: E402
from common_q383 import U, Checks, open_page  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

VIEWS_JS = r"""() => {
  const U = window.NMSKUltrasound, L = window.NMSKUltrasoundLib, geo = U.geo();
  const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]], add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]], mul = (a, s) => [a[0] * s, a[1] * s, a[2] * s];
  const dot = L.dot, cross = L.cross, unit = L.unit;
  const find = re => { const rx = new RegExp(re); for (let i = 0; i < geo.n; i++) { const id = String((geo.recs[i] && geo.recs[i].id) || ''); if (rx.test(id)) return i; } return -1; };
  const verts = (sid, step) => { const out = [], v0 = geo.vStart[sid], v1 = geo.vStart[sid + 1]; for (let k = v0; k < v1; k += (step || 1)) out.push([geo.pos[3 * k], geo.pos[3 * k + 1], geo.pos[3 * k + 2]]); return out; };
  const cen = sid => { const v = verts(sid); let c = [0, 0, 0]; v.forEach(p => { c = add(c, p); }); return mul(c, 1 / v.length); };
  const axis = sid => L.pcaAxis(geo.pos, geo.vStart[sid], geo.vStart[sid + 1]).a;
  const perp = (v, a) => sub(v, mul(a, dot(v, a)));
  function limb(muscleRe, boneRe, along, frac) {              // over a muscle, square to the bone under it; the probe's long side along / across the bone
    const m = find(muscleRe), bn = find(boneRe); if (m < 0 || bn < 0) return {err: 'missing ' + muscleRe + ' / ' + boneRe};
    const a = axis(bn); let c = cen(m);
    const vs = verts(m), q = vs.map(p => dot(p, a)), lo = Math.min(...q), hi = Math.max(...q), want = lo + frac * (hi - lo), near = vs.filter(p => Math.abs(dot(p, a) - want) < 6);
    if (near.length) { c = [0, 0, 0]; near.forEach(p => { c = add(c, p); }); c = mul(c, 1 / near.length); }
    const o = unit(perp(sub(c, cen(bn)), a));
    return {T: c, out: o, u: along ? a : unit(cross(o, a))};
  }
  const views = {
    thigh_trans: () => Object.assign(limb('^rectus_femoris_r$', '^femur_r$', false, 0.5), {freq: 10, depthCm: 5.5}),
    thigh_long: () => Object.assign(limb('^rectus_femoris_r$', '^femur_r$', true, 0.5), {freq: 10, depthCm: 5.5}),
    calf_trans: () => Object.assign(limb('^gastrocnemius_r$', '^tibia_r$', false, 0.45), {freq: 8, depthCm: 6}),
    forearm_trans: () => Object.assign(limb('^flexor_digitorum_superficialis_r$', '^radius_r$', false, 0.35), {freq: 12, depthCm: 3.5}),
    carpal_trans: () => { const fr = find('^flexor_retinaculum_r$'), cap = find('^(zan_)?capitate(_bone)?_r$'), rad = find('^radius_r$'); if (fr < 0 || cap < 0 || rad < 0) return {err: 'missing carpal'};
      const a = axis(rad), c = cen(fr), o = unit(perp(sub(c, cen(cap)), a)); return {T: c, out: o, u: unit(cross(o, a)), freq: 15, depthCm: 2.5}; },
    supra_long: () => { const m = find('^supraspinatus_r$'), hu = find('^humerus_r$'); if (m < 0 || hu < 0) return {err: 'missing supraspinatus'};
      const vs = verts(m), ah = axis(hu), hv = verts(hu, 3), q = hv.map(p => dot(p, ah)), up = dot(ah, [0, 1, 0]) > 0 ? 1 : -1, top = up > 0 ? Math.max(...q) : Math.min(...q);
      let hc = [0, 0, 0], n = 0; hv.forEach((p, i) => { if (Math.abs(q[i] - top) < 40) { hc = add(hc, p); n++; } }); hc = mul(hc, 1 / n);
      const srt = vs.map(p => [Math.hypot(p[0] - hc[0], p[1] - hc[1], p[2] - hc[2]), p]).sort((x, y) => x[0] - y[0]).slice(0, Math.max(8, Math.floor(vs.length * 0.06)));
      let ins = [0, 0, 0]; srt.forEach(e => { ins = add(ins, e[1]); }); ins = mul(ins, 1 / srt.length);
      const o = unit(sub(ins, hc)); return {T: ins, out: o, u: unit(perp(axis(m), o)), freq: 12, depthCm: 3.5}; }
  };
  const b64 = u8 => { let s = ''; for (let i = 0; i < u8.length; i += 32768) s += String.fromCharCode.apply(null, u8.subarray(i, Math.min(u8.length, i + 32768))); return btoa(s); };
  async function capture(nm) {
    const v = views[nm](); if (v.err) return v;
    const h = U.placeRay(add(v.T, mul(v.out, 400)), mul(v.out, -1)); if (!h) return {err: 'no skin'};
    const u0 = L.probeFrame(h.N, L.REF.long, 0, 0, 0).u, ud = unit(perp(v.u, h.N)), rot = (Math.atan2(dot(cross(u0, ud), h.N), dot(u0, ud)) * 180 / Math.PI + 360) % 360;
    U.set({probe: 'linear'}); U.set({refKey: 'long', rot: rot, freq: v.freq, depthCm: v.depthCm, focusCm: v.depthCm * 0.5, gain: 0, dr: 60, tgc: 0, mTilt: 0, speckle: true, textures: true, reverb: true, noise: false});
    let fr = null, ms = 1e9, kms = 1e9;
    for (let i = 0; i < 3; i++) { fr = await U.frameNow({}, {maxDim: 480, maxLines: 256}); ms = Math.min(ms, fr.simMs); kms = Math.min(kms, fr.kms); }
    let live = 1e9; for (let i = 0; i < 3; i++) { const f2 = await U.frameNow({}, {maxDim: 320, maxLines: 192}); live = Math.min(live, f2.simMs + f2.kms); }
    const sim = fr.sim, gray = L.toGray(sim.db, U.table().global.display_ref_fraction, 0, 60), meta = {};
    const seen = {}; for (let i = 0; i < fr.sid.length; i += 3) seen[fr.sid[i]] = 1;
    Object.keys(seen).forEach(k => { const q = +k; if (q < geo.n) meta[q] = (geo.recs[q] && geo.recs[q].id) || ''; });
    return {P: h.P, rot: rot, Wo: sim.Wo, Ho: sim.Ho, W: fr.plan.W, H: fr.plan.H, plan: fr.plan, freq: v.freq, depthMm: v.depthCm * 10, contact: sim.contact, simMs: ms, kms: kms, liveMs: live, lat5: sim.latFw(5), lat20: sim.latFw(20),
      gray: b64(new Uint8Array(gray.buffer)), db: b64(new Uint8Array(sim.db.buffer)), lab: b64(fr.lab), sid: b64(new Uint8Array(fr.sid.buffer, fr.sid.byteOffset, fr.sid.byteLength)), ids: meta,
      keys: window.NMSKImaging.table().classes.map(c => c.key)};
  }
  window.Q383V = {names: Object.keys(views), capture};
}"""


def fmt(v):
    return "none" if v is None or (isinstance(v, float) and v != v) else ("%.1f" % v if isinstance(v, float) else str(v))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("build_dir")
    ap.add_argument("--shots", default=None)
    ap.add_argument("--tag", default="after")
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args()
    d = Path(a.build_dir).resolve()
    shots = Path(a.shots) if a.shots else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
    check = Checks(); page_errors: list[str] = []
    T = f"[{d.name}]"
    print(f"=== Q383 image: {d.name} ({a.tag}) ===")
    res = {}
    with sync_playwright() as pl:
        srv, b, pg = open_page(pl, d, 1400, 900, page_errors)
        try:
            pg.evaluate(f"() => {U}.ready()")
            pg.evaluate(VIEWS_JS)
            for nm in pg.evaluate("() => window.Q383V.names"):
                r = pg.evaluate("async (nm) => await window.Q383V.capture(nm)", nm)
                if not r or r.get("err"):
                    check(f"{T} {nm}: the view can be seated ({r})", a.report_only); continue
                Wo, Ho, W, H = r["Wo"], r["Ho"], r["W"], r["H"]
                db = np.frombuffer(base64.b64decode(r["db"]), dtype=np.float32).reshape(Ho, Wo)
                lab = np.frombuffer(base64.b64decode(r["lab"]), dtype=np.uint8).reshape(H, W)
                sid = np.frombuffer(base64.b64decode(r["sid"]), dtype=np.uint16).reshape(H, W)
                if shots:
                    Image.frombytes("L", (Wo, Ho), base64.b64decode(r["gray"])).save(shots / f"q383_{d.name}_{a.tag}_{nm}.png")
                m = M.measure(db, lab, sid, r["plan"], r["keys"], max_depth_mm=min(r["depthMm"], 900.0 / (2 * 1.0 * r["freq"])))
                m.update({k: r[k] for k in ("simMs", "kms", "liveMs", "lat5", "lat20", "contact")})
                res[nm] = m
                print(f"     {nm}: muscle {fmt(m['muscle_db'])} dB, fat {fmt(m['fat_db'])} | septum n {m['septum_n']} +{fmt(m['septum_median_over_muscle_db'])} dB found {fmt(m['septum_found_frac'] * 100 if m['septum_n'] else None)} % | "
                      f"sheath n {m['sheath_n']} found {fmt(m['sheath_found_frac'] * 100 if m['sheath_n'] else None)} % | fascia n {m['fascia_n']} peak {fmt(m['fascia_peak_db'])} dB found {fmt(m['fascia_found_frac'] * 100 if m['fascia_n'] else None)} % | "
                      f"bone edge {fmt(m['bone_edge_db'])} shadow {fmt(m['shadow_db'])} (n {m['bone_n']}/{m['shadow_n']}) | top/bottom {fmt(m.get('muscle_top_db'))}/{fmt(m.get('muscle_bottom_db'))} | lines {fmt(m.get('line_persistence'))} @ {m.get('line_angle_deg')}° | "
                      f"beam {m['lat5']:.2f} mm @5, {m['lat20']:.2f} @20 | kernel {m['simMs']} ms + slice {m['kms']} ms, live tier {m['liveMs']} ms")
        finally:
            b.close(); srv.terminate()
    if shots:
        (shots / f"q383_{d.name}_{a.tag}_metrics.json").write_text(json.dumps(res, indent=1))
    if not a.report_only:
        check(f"{T} all six views seated with skin contact ({sorted(res)})", len(res) == 6 and all(v["contact"] for v in res.values()))
        for nm, m in res.items():
            V = f"{T} {nm}:"
            if m["septum_n"] >= 20:
                need = 0.6 if nm == "supra_long" else 0.9
                check(f"{V} 1 a bright line on {m['septum_found_frac'] * 100:.0f} % of the {m['septum_n']} muscle | muscle boundary samples (>= {need * 100:.0f} %), median {m['septum_median_over_muscle_db']:.1f} dB above the muscle beside it",
                      m["septum_found_frac"] >= need and m["septum_median_over_muscle_db"] >= 10)
            if m["sheath_n"] >= 20:
                check(f"{V} 1 a bright line on {m['sheath_found_frac'] * 100:.0f} % of the {m['sheath_n']} sheath samples (>= 85 %)", m["sheath_found_frac"] >= 0.85)
            if m["fascia_n"] >= 20:
                check(f"{V} 1 a bright line on {m['fascia_found_frac'] * 100:.0f} % of the {m['fascia_n']} fascia-mesh samples (>= 80 %)", m["fascia_found_frac"] >= 0.8)
                check(f"{V} 2 brightness order: fat {fmt(m['fat_db'])} < fascia line {m['fascia_peak_db']:.1f} dB and muscle {m['muscle_db']:.1f} < fascia line (by >= 6 / 12 dB)",
                      m["fascia_peak_db"] >= m["muscle_db"] + 12 and (m["fat_px"] < 50 or m["fascia_peak_db"] >= m["fat_db"] + 6))
            if m["bone_n"] >= 20:
                check(f"{V} 2 the cortex is a bright line ({m['bone_edge_db']:.1f} dB, muscle {m['muscle_db']:.1f}: >= +20)", m["bone_edge_db"] >= m["muscle_db"] + 20)
            if m["shadow_n"] >= 20:
                check(f"{V} 2 a clean shadow 3-8 mm below the cortex ({m['shadow_db']:.1f} dB, muscle {m['muscle_db']:.1f}: <= -25)", m["shadow_db"] <= m["muscle_db"] - 25)
            if m.get("muscle_top_db") is not None and m["muscle_px"] > 3000:
                check(f"{V} 3 muscle reads alike with depth (upper half {m['muscle_top_db']:.1f}, lower half {m['muscle_bottom_db']:.1f} dB: within 6)", abs(m["muscle_top_db"] - m["muscle_bottom_db"]) <= 6)
            check(f"{V} 5 the beam of an array: {m['lat5']:.2f} mm wide at 5 mm depth (<= 1 mm)", m["lat5"] <= 1.0)
        if "thigh_long" in res and "thigh_trans" in res:
            lg, tr = res["thigh_long"]["line_persistence"], res["thigh_trans"]["line_persistence"]
            check(f"{T} 4 along the fibres the bright marks run on as lines (thigh longitudinal {lg:.2f} at {res['thigh_long']['line_angle_deg']}°), across them they do not (thigh transverse {tr:.2f})", lg >= 0.18 and lg >= tr + 0.12)
            for nm in ("calf_trans", "forearm_trans"):
                if nm in res and res[nm].get("line_persistence") is not None:
                    check(f"{T} 4 {nm}: across the fibres, no lines ({res[nm]['line_persistence']:.2f} <= 0.15)", res[nm]["line_persistence"] <= 0.15)
        if res:
            worst = max(v["simMs"] + v["kms"] for v in res.values()); live = max(v["liveMs"] for v in res.values())
            check(f"{T} 5 frame time: 480 tier <= {worst} ms, live tier <= {live} ms per frame (budget 400 / 200 ms in this software-rendered browser; before Q383 on the same machine: see the 'before' report)", worst <= 400 and live <= 200)
    check(f"no page error ({page_errors[:2]})", not page_errors)
    print(f"{check.n - len(check.errs)} OK, {len(check.errs)} FAIL")
    print("Q383_IMAGE_OK" if not check.errs else "Q383_IMAGE_FAIL")
    return 0 if not check.errs else 1


if __name__ == "__main__":
    sys.exit(main())
