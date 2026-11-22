"""Q384 verifier, part H (E5): finger abduction / adduction, thumb axial rotation, thumb opposition. See verify_pose_q384.py.

Owner, 2026-11-22: "in the fingers there is also abduction and adduction, and in the thumb also opposition."
Ranges: docs/pose_rom_table.md `finger_mcp_abd` (an ASSUMPTION, labelled so) and `thumb_cmc_rot` (Cooney 1981); the
Opposition control drives CMC flexion, palmar abduction and rotation together -- a display convention, labelled so."""
from __future__ import annotations

import numpy as np

JS = """() => { const P = window.__poseApi, Q = window.__q384, rig = P.rig(), J = {}; rig.joints.forEach(j => J[j.id] = j);
  const dist = (a, b) => { const x = Q.world(a), y = Q.world(b); return Math.hypot(x[0]-y[0], x[1]-y[1], x[2]-y[2]); };
  const out = {rom: [rig.rom.finger_mcp_abd, rig.rom.thumb_cmc_rot], sides: {}};
  for (const s of ['l', 'r']){
    const o = {dof: {}};
    for (const k of [2, 3, 4, 5]) o.dof['f' + k] = J['f' + k + '_mcp_' + s].dof.map(d => [d.k, d.lo, d.hi, d.rk]);
    o.dof.thumb = J['thumb_cmc_' + s].dof.map(d => [d.k, d.lo, d.hi, d.rk]); o.couple = J['thumb_cmc_' + s].couple || null;
    P.reset(); P.update();
    const d0 = {i: dist('f2_dip_' + s, 'f3_dip_' + s), l: dist('f5_dip_' + s, 'f3_dip_' + s), r: dist('f4_dip_' + s, 'f3_dip_' + s)};
    P.set('f2_mcp_' + s, 'abd', 20); const iAb = dist('f2_dip_' + s, 'f3_dip_' + s), fx = P.pose().j['f2_mcp_' + s][0];
    P.set('f2_mcp_' + s, 'abd', -99); const iAd = dist('f2_dip_' + s, 'f3_dip_' + s), clampLo = P.pose().j['f2_mcp_' + s][1];
    P.set('f2_mcp_' + s, 'abd', 0);
    P.set('f5_mcp_' + s, 'abd', 99); const lAb = dist('f5_dip_' + s, 'f3_dip_' + s), clampHi = P.pose().j['f5_mcp_' + s][1];
    P.set('f5_mcp_' + s, 'abd', 0);
    P.set('f4_mcp_' + s, 'abd', 20); const rAb = dist('f4_dip_' + s, 'f3_dip_' + s); P.set('f4_mcp_' + s, 'abd', 0);
    P.set('f3_mcp_' + s, 'abd', 20); const mAb = dist('f3_dip_' + s, 'f2_dip_' + s); P.set('f3_mcp_' + s, 'abd', 0);
    o.fingers = {d0, iAb, iAd, lAb, rAb, mAb, m0: d0.i, fx, fx0: J['f2_mcp_' + s].dof[0].q0, clampLo, clampHi};
    P.reset(); P.update();
    P.setCouple('thumb_cmc_' + s, 'opp', 0); const p0 = P.pose().j['thumb_cmc_' + s].slice(), t0 = dist('thumb_ip_' + s, 'f5_mcp_' + s), v0 = P.coupleValue('thumb_cmc_' + s, 'opp');
    P.setCouple('thumb_cmc_' + s, 'opp', 100); const p1 = P.pose().j['thumb_cmc_' + s].slice(), t1 = dist('thumb_ip_' + s, 'f5_mcp_' + s), v1 = P.coupleValue('thumb_cmc_' + s, 'opp');
    P.setCouple('thumb_cmc_' + s, 'opp', 50); const p5 = P.pose().j['thumb_cmc_' + s].slice();
    P.reset(); P.update();
    const seg = J['thumb_cmc_' + s].seg, A = P.matrices()[seg].slice(), m0 = Q.world('thumb_mcp_' + s);
    P.set('thumb_cmc_' + s, 'rot', 17); const B = P.matrices()[seg].slice(), m1 = Q.world('thumb_mcp_' + s);
    const tr = A[0]*B[0] + A[1]*B[1] + A[2]*B[2] + A[4]*B[4] + A[5]*B[5] + A[6]*B[6] + A[8]*B[8] + A[9]*B[9] + A[10]*B[10];
    o.thumb = {p0, p1, p5, t0, t1, v0, v1, rotDeg: Math.acos(Math.max(-1, Math.min(1, (tr - 1) / 2))) * 180 / Math.PI, mcpShift: Math.hypot(m1[0]-m0[0], m1[1]-m0[1], m1[2]-m0[2])};
    P.reset(); P.update();
    P.ringHold('f2_mcp_' + s); let st = P.ringState(); o.ringF = [st.rings, st.handles.length];
    P.ringHold('thumb_cmc_' + s); st = P.ringState(); o.ringT = [st.rings, st.handles.length];
    P.ringHold(null);
    out.sides[s] = o;
  }
  P.open(true);
  const rows = g => { const sec = [...document.querySelectorAll('#pz-body .pz-g')].filter(x => (x.querySelector('.pz-gh') || {}).textContent === g)[0];
    return sec ? [...sec.querySelectorAll('.pz-row')].map(r => ({lab: r.querySelector('.pz-lab').textContent, cells: r.querySelectorAll('.pz-cell').length, note: (r.querySelector('.pz-cnote') || {}).textContent || ''})) : []; };
  out.panel = {fingers: rows('Fingers'), thumb: rows('Thumb')};
  P.panelView({solo: true}); P.ringHold('thumb_cmc_l');
  out.solo = [...document.querySelectorAll('#pz-body input[type=range]')].filter(e => e.offsetParent !== null).map(e => e.getAttribute('aria-label'));
  P.ringHold(null); P.panelView({solo: false, mini: false, forget: true}); P.open(false); P.reset(); P.update();
  return out; }"""


def run(pg, check):
    print("H. fingers: abduction / adduction; thumb: axial rotation and opposition (E5)", flush=True)
    pg.evaluate("() => { const P = window.__poseApi; P.reset(); P.update(); P.open(true); P.open(false); }")
    o = pg.evaluate(JS)
    fa, tr = o["rom"]
    check("the ranges are the table's: finger_mcp_abd %s..%s (labelled an assumption: %s), thumb_cmc_rot %s..%s (Cooney 1981: %s)" % (
        fa[0], fa[1], "ASSUMPTION" in fa[3], tr[0], tr[1], "Cooney 1981" in tr[3]), fa[:2] == [-20, 20] and "ASSUMPTION" in fa[3] and tr[:2] == [0, 17] and "Cooney 1981" in tr[3])
    for s, d in o["sides"].items():
        S = s.upper()
        ok = all([x[0] for x in d["dof"]["f%d" % k]] == ["flex", "abd"] and d["dof"]["f%d" % k][1][1:] == [-20, 20, "finger_mcp_abd"] for k in (2, 3, 4, 5))
        check("%s: the four finger MCP joints have flexion and abduction / adduction (-20..20)" % S, ok)
        f = d["fingers"]
        check("%s: abducting the index finger takes its tip away from the middle finger (%.1f -> %.1f mm), adducting brings it back past rest (%.1f); flexion untouched (%.1f)" % (
            S, f["d0"]["i"], f["iAb"], f["iAd"], f["fx"]), f["iAb"] > f["d0"]["i"] + 5 and f["iAd"] < f["d0"]["i"] - 3 and abs(f["fx"] - f["fx0"]) < 1e-6)
        check("%s: the little and the ring finger abduct away from the middle finger too (%.1f -> %.1f, %.1f -> %.1f mm); the middle finger's (+) goes towards the index (%.1f -> %.1f)" % (
            S, f["d0"]["l"], f["lAb"], f["d0"]["r"], f["rAb"], f["m0"], f["mAb"]), f["lAb"] > f["d0"]["l"] + 5 and f["rAb"] > f["d0"]["r"] + 3 and f["mAb"] < f["m0"] - 3)
        check("%s: the range holds (asked -99 / +99, got %.0f / %.0f)" % (S, f["clampLo"], f["clampHi"]), f["clampLo"] == -20 and f["clampHi"] == 20)
        t = d["thumb"]
        check("%s: thumb CMC has flexion, palmar abduction and axial rotation (%s)" % (S, [x[0] for x in d["dof"]["thumb"]]),
              [x[0] for x in d["dof"]["thumb"]] == ["flex", "abd", "rot"] and d["dof"]["thumb"][2][1:] == [0, 17, "thumb_cmc_rot"])
        check("%s: axial rotation turns the thumb metacarpal by %.1f deg about its own axis (the MCP centre moves %.2f mm)" % (S, t["rotDeg"], t["mcpShift"]), abs(t["rotDeg"] - 17) < 0.5 and t["mcpShift"] < 1.0)
        cp = (d["couple"] or [{}])[0]
        check("%s: Opposition 0 %% = %s, 100 %% = %s, 50 %% = %s (flexion, abduction, rotation, each over its own range); reads back %.0f / %.0f" % (
            S, [round(x, 1) for x in t["p0"]], [round(x, 1) for x in t["p1"]], [round(x, 1) for x in t["p5"]], t["v0"], t["v1"]),
            np.allclose(t["p0"], [-20, 0, 0], atol=0.01) and np.allclose(t["p1"], [15, 42, 17], atol=0.01) and np.allclose(t["p5"], [-2.5, 21, 8.5], atol=0.01)
            and round(t["v0"]) == 0 and round(t["v1"]) == 100 and cp.get("convention"))
        check("%s: opposition carries the thumb towards the little finger (thumb IP to little-finger MCP %.1f -> %.1f mm)" % (S, t["t0"], t["t1"]), t["t1"] < t["t0"] - 10)
        check("%s: the rings: finger MCP %s with %d handles, thumb CMC %s with %d handles" % (S, [r[1] for r in d["ringF"][0]], d["ringF"][1], [r[1] for r in d["ringT"][0]], d["ringT"][1]),
              [r[1] for r in d["ringF"][0]] == ["flex", "abd"] and d["ringF"][1] == 2 and [r[1] for r in d["ringT"][0]] == ["flex", "abd", "rot"] and d["ringT"][1] == 3)
    pf, pt = o["panel"]["fingers"], o["panel"]["thumb"]
    ab = [r for r in pf if "abduction" in r["lab"] or "thumb side" in r["lab"]]
    check("panel, Fingers: an abduction / adduction row for each of the four fingers, both sides (%d rows: %s)" % (len(ab), [r["lab"][:34] for r in ab][:4]), len(ab) == 4 and all(r["cells"] == 2 for r in ab))
    op = [r for r in pt if "Opposition" in r["lab"]]
    check("panel, Thumb: rotation and Opposition rows; Opposition says it is a display convention (%s)" % (op[0]["note"][:70] if op else None),
          any("axial rotation" in r["lab"] for r in pt) and len(op) == 1 and op[0]["cells"] == 2 and "display convention" in op[0]["note"])
    check("'This joint only' on the thumb CMC shows its four sliders (%s)" % [x.split(" ")[2] if len(x.split(" ")) > 2 else x for x in o["solo"]], len(o["solo"]) == 4 and any("Opposition" in x for x in o["solo"]))
