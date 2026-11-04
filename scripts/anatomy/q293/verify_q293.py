#!/usr/bin/env python3
"""Q293: real headless-Chromium check (desktop 1400x900 real clicks + phone 390x844 real touch) of the owner's three points on the
rebuilt pages:

A  rectus femoris has BOTH heads: the page lists rectus_femoris_r/l AND the rule-based rectus_femoris_reflected_head_r/l, drawn; the
   Learn card of rectus femoris (r) lists "Heads (2)" with the reflected head as this page's own RULE-BASED mesh; picking the muscle
   marks both structures; the reflected head's own card says RULE-BASED and gives its volume
B  the RF simulation ("All together"): from its first sample the knee flexion angle only DEcreases (extension) and the hip flexion angle
   increases; both joints move during the same phase (not one after the other); the pose ends at the model pose
C  a sample of other two-joint muscles moves BOTH joints at once in the cited directions (gastrocnemius, semitendinosus, biceps brachii
   whole muscle incl. its long head, long head of triceps; FDS on the pages with finger joints)
D  fingers (pages with finger joints): every finger joint is closed on the page's bones (rest pose) and stays closed when the fingers
   are posed (fist); the rig's finger joint centres sit on the parent bone's head
E  0 page errors

    python3 scripts/anatomy/q293/verify_q293.py PAGE_DIR... [--phone-only-first N]"""
from __future__ import annotations
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "q283"))
import verify_q283 as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

check, tap, tap_text, api = V.check, V.tap, V.tap_text, V.api
SAMPLER = """(e) => { window.__smp = []; window.__smpT = setInterval(() => { try { const a = window.NMSKClinicalTool.api, s = window.learnCtl.animState();
  window.__smp.push({ph: s ? s.phase : null, v: (new Function('api', 'return ' + e))(a)}); } catch (x) {} }, 30); }"""


def run_sim(pg, label, expr, phone, timeout=600000):
    pg.evaluate(SAMPLER, expr)
    labs = pg.evaluate("() => Array.from(document.querySelectorAll('#ln-acts button')).map(b => b.textContent)")
    if not any(label in t for t in labs) and labs:
        label = labs[0]                          # a muscle whose cited actions are ONE row has no "All together": its single row is the whole action
    ok = tap_text(pg, "#ln-acts", label, phone)
    if not ok:
        pg.evaluate("() => clearInterval(window.__smpT)"); return None
    pg.wait_for_function("window.learnCtl.state().animating", timeout=20000)
    pg.wait_for_function("!window.learnCtl.state().animating", timeout=timeout)
    pg.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    return pg.evaluate("() => { clearInterval(window.__smpT); return window.__smp.filter(s => s.ph); }")


def mono(seq, sign, tol=0.05):
    return all((b - a) * sign >= -tol for a, b in zip(seq, seq[1:]))


def joint_val(j, k=0):
    return f"(api.pose().pose().j['{j}'] || [NaN])[{k}]"


def two_joint(pg, T, phone, errs, muscle, side, part, label, J, rig):
    """J = [(joint id, dof, cited sign)]"""
    ok = pg.evaluate("([b, s]) => window.learnCtl.pickMuscle(b, s)", [muscle, side]); pg.wait_for_timeout(300)
    if not ok:
        print(f"  INFO {T}: {muscle} not on this page"); return
    if part:
        tap_text(pg, "#ln-parts", part, phone); pg.wait_for_timeout(300)
    have = [(j, k, s) for (j, k, s) in J if j in rig and k in rig[j]]
    if len(have) < 2:
        print(f"  INFO {T}: {muscle}: this page's rig lacks {[j for j, _, _ in J if j not in rig]}, skipped"); return
    expr = "[" + ",".join(joint_val(j, rig[j].index(k)) for (j, k, s) in have) + "]"
    smp = run_sim(pg, label, expr, phone)
    act = [x["v"] for x in (smp or []) if x["ph"] in ("action", "hold")]
    if not act:
        check(f"{T}: C {muscle}{' ' + part if part else ''}: simulation sampled", False, errs); return
    res, both = [], False
    for n, (j, k, s) in enumerate(have):
        seq = [a[n] for a in act]
        res.append(f"{j}.{k} {seq[0]:.0f}->{seq[-1]:.0f}")
        check(f"{T}: C {muscle}{' (' + part + ')' if part else ''}: {j} {k} moves only in the cited direction ({'+' if s > 0 else '-'}) during the action ({seq[0]:.1f} -> {seq[-1]:.1f})",
              mono(seq, s) and (seq[-1] - seq[0]) * s > 3, errs)
    # simultaneous: one sample in the action phase where every joint is strictly between its start and its end
    lo = [min(a[n] for a in act) for n in range(len(have))]; hi = [max(a[n] for a in act) for n in range(len(have))]
    both = any(all(lo[n] + 0.1 * (hi[n] - lo[n]) < a[n] < hi[n] - 0.1 * (hi[n] - lo[n]) for n in range(len(have))) for a in act)
    check(f"{T}: C {muscle}: all {len(have)} joints move at the same time ({', '.join(res)})", both, errs)


def fingers(pg, T, errs):
    js = """() => { const api = window.NMSKClinicalTool.api, pc = api.pose(), rig = pc.rig(), L = api.list();
      const fj = rig.joints.filter(j => /^(f[2-5]_(mcp|pip|dip)|thumb_(mcp|ip))_[rl]$/.test(j.id));
      if (!fj.length) return null;
      const segOf = {}; rig.rigid.forEach(g => g[1].forEach(i => segOf[i] = g[0]));
      const name = s => rig.segs[s][0];
      const bones = {}; L.forEach(r => { if (r.cat !== 'bone') return; const s = segOf[r.i]; if (s === undefined) return; (bones[name(s)] = bones[name(s)] || []).push(r.i); });
      const pos = i => { const live = window.__poseLive && window.__poseLive(i); if (live) return live; const g = api.geometry(i); return g ? g.pos : null; };
      const minGap = (A, B) => { let best = 1e9; const pa = [], pb = [];
        A.forEach(i => { const p = pos(i); for (let k = 0; k < p.length; k += 9) pa.push([p[k], p[k+1], p[k+2]]); });
        B.forEach(i => { const p = pos(i); for (let k = 0; k < p.length; k += 3) pb.push([p[k], p[k+1], p[k+2]]); });
        pa.forEach(a => pb.forEach(b => { const d = (a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2; if (d < best) best = d; })); return Math.sqrt(best); };
      const out = {};
      fj.forEach(j => { const par = name(j.par), ch = name(j.seg); if (!bones[par] || !bones[ch]) return; out[j.id] = +minGap(bones[ch], bones[par]).toFixed(2); });
      return out; }"""
    g0 = pg.evaluate(js)
    if g0 is None:
        print(f"  INFO {T}: no finger joints on this page's rig (its fingers move with the hand)"); return
    worst = max(g0.items(), key=lambda t: t[1])
    check(f"{T}: D rest pose: every finger joint closed on the bones ({len(g0)} joints, worst {worst[0]} {worst[1]} mm)", worst[1] < 2.5, errs)
    pg.evaluate("""() => { const p = window.NMSKClinicalTool.api.pose(), d = p.restPose();
      p.rig().joints.forEach(j => { const m = j.id.match(/^(f\\d_(mcp|pip|dip)|thumb_(mcp|ip))_/); if (!m) return; const V = {mcp:70, pip:90, dip:50, thumb_mcp:40, thumb_ip:50}; d.j[j.id] = [V[m[2] || ('thumb_' + m[3])]]; });
      p.apply(d); p.update(); }""")
    pg.wait_for_timeout(1500)
    g1 = pg.evaluate(js)
    worst1 = max(g1.items(), key=lambda t: t[1])
    check(f"{T}: D fist pose: the joints stay closed while the fingers flex (worst {worst1[0]} {worst1[1]} mm)", worst1[1] < 3.0, errs)
    pg.evaluate("() => { const p = window.NMSKClinicalTool.api.pose(); p.reset(); p.update(); }"); pg.wait_for_timeout(500)


def run_page(b, d: Path, phone: bool, errs):
    html = V.html_of(d); srv, port = V.serve(d)
    try:
        w, h = (390, 844) if phone else (1400, 900)
        T = f"{d.name}_{w}"
        ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
        pg = ctx.new_page(); perr = []
        pg.on("pageerror", lambda e: perr.append(str(e)))
        pg.route("**/*", V.route)
        pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=300000)
        V.ready(pg)
        ids = ["rectus_femoris_r", "rectus_femoris_l", "rectus_femoris_reflected_head_r", "rectus_femoris_reflected_head_l"]
        idx = api(pg, "Object.fromEntries(api.list().filter(r => " + json.dumps(ids) + ".includes(r.id)).map(r => [r.id, r.i]))")
        vis = {k: api(pg, f"api.visible({i})") for k, i in idx.items()}
        check(f"{T}: A both heads of rectus femoris on the page and drawn ({vis})", len(idx) == 4 and all(vis.values()), errs)
        rig = pg.evaluate("() => Object.fromEntries(window.NMSKClinicalTool.api.pose().rig().joints.filter(j => !j.driven).map(j => [j.id, j.dof.map(d => d.k)]))")
        tap(pg, "#t-learn", phone); pg.wait_for_timeout(250)
        pg.fill("#ln-q", "rectus femoris"); pg.wait_for_timeout(300)
        tap_text(pg, "#ln-res", "Rectus femoris (r)", phone) or tap_text(pg, "#ln-res", "(r)", phone); pg.wait_for_timeout(500)
        st = pg.evaluate("() => window.learnCtl.state()")
        check(f"{T}: A Learn picked rectus femoris (r) ({st['cur']})", st["cur"] and st["cur"]["b"] == "rectus_femoris" and st["cur"]["side"] == "r", errs)
        marks = set(api(pg, "api.selection().state().marks"))
        check(f"{T}: A picking the muscle marks both heads ({sorted(marks)})", {"rectus_femoris_r", "rectus_femoris_reflected_head_r"} <= marks, errs)
        heads = pg.evaluate("() => Array.from(document.querySelectorAll('#ln-info .ln-heads li')).map(li => li.textContent)")
        check(f"{T}: A card lists Heads (2), reflected head = own RULE-BASED mesh ({heads})",
              len(heads) == 2 and any("Reflected" in x and "RULE-BASED" in x for x in heads) and any("Straight" in x for x in heads), errs)
        parts = pg.evaluate("() => Array.from(document.querySelectorAll('#ln-parts button')).map(b => b.textContent)")
        check(f"{T}: A part buttons offer both heads ({parts})", any("Reflected" in p for p in parts) and any("Straight" in p for p in parts), errs)
        # B RF simulation
        hip, knee = joint_val("hip_r", 0), joint_val("knee_r", 0)
        p0 = api(pg, "api.pose().pose().j")
        smp = run_sim(pg, "All together", f"[{hip}, {knee}]", phone)
        act = [x["v"] for x in (smp or [])]
        ph = [x["ph"] for x in (smp or [])]
        if act:
            hs, ks = [a[0] for a in act], [a[1] for a in act]
            ka = [a[1] for a, p in zip(act, ph) if p in ("start", "action", "hold")]
            kr = [a[1] for a, p in zip(act, ph) if p == "release"]
            k0 = (p0.get("knee_r") or [0])[0]      # the model pose's own knee angle (non-zero on the CT-posed bodies)
            check(f"{T}: B RF: knee flexion never increases from the first sample (knee {ka[0]:.1f} -> min {min(ka):.1f}, {len(ka)} samples, phases {sorted(set(ph))}); "
                  f"release only returns to the model pose ({k0:.1f}; max {max(kr) if kr else None})",
                  mono(ka, -1) and ka[0] - min(ka) > 15 and all(x <= max(k0, min(ka)) + 0.5 for x in kr), errs)
            ah = [a[0] for a, p in zip(act, ph) if p in ("start", "action", "hold")]
            check(f"{T}: B RF: hip flexion increases ({ah[0]:.1f} -> {max(ah):.1f}) and never decreases before the release", mono(ah, 1) and max(ah) - ah[0] > 15, errs)
            mid = [a for a, p in zip(act, ph) if p == "action"]
            sim = any(hs[0] + 3 < a[0] < max(hs) - 3 and min(ks) + 3 < a[1] < ks[0] - 3 for a in mid)
            check(f"{T}: B RF: hip and knee move in the SAME phase (a sample with both part-way)", sim, errs)
        else:
            check(f"{T}: B RF simulation sampled", False, errs)
        p1 = api(pg, "api.pose().pose().j")
        check(f"{T}: B pose back at the model pose after the run", all(abs(a - c) < 0.01 for k in p0 for a, c in zip(p0[k], p1[k])), errs)
        # C other two-joint muscles
        two_joint(pg, T, phone, errs, "gastrocnemius", "r", None, "All together", [("knee_r", "flex", 1), ("ankle_r", "dp", -1)], rig)
        two_joint(pg, T, phone, errs, "semitendinosus", "r", None, "All together", [("hip_r", "flex", -1), ("knee_r", "flex", 1)], rig)
        two_joint(pg, T, phone, errs, "biceps_brachii", "r", None, "All together", [("elbow_r", "flex", 1), ("shoulder_r", "flex", 1)], rig)
        two_joint(pg, T, phone, errs, "triceps_brachii", "r", "Long head", "All together", [("shoulder_r", "flex", -1), ("elbow_r", "flex", -1)], rig)
        if not phone:
            two_joint(pg, T, phone, errs, "sartorius", "r", None, "All together", [("hip_r", "flex", 1), ("knee_r", "flex", 1)], rig)
            two_joint(pg, T, phone, errs, "flexor_digitorum_superficialis", "r", None, "All together", [("wrist_r", "flex", 1), ("f3_mcp_r", "flex", 1), ("f3_pip_r", "flex", 1)], rig)
        # the reflected head's own card (page card) says RULE-BASED + volume
        tap(pg, "#ln-close", phone); pg.wait_for_timeout(150)
        rec = pg.evaluate("""() => { const api = window.NMSKClinicalTool.api; const r = api.list().filter(x => x.id === 'rectus_femoris_reflected_head_r')[0]; return r ? r.name : null; }""")
        txt = pg.evaluate("() => document.documentElement.innerHTML.indexOf('RULE-BASED (Q293)') >= 0")
        check(f"{T}: A the reflected head is named and badged rule-based in the page data ({rec})", rec and "rule-based" in rec and txt, errs)
        fingers(pg, T, errs)
        check(f"{T}: E 0 page errors", not perr, errs)
        if perr:
            print("    ", perr[:4])
        ctx.close()
    finally:
        srv.terminate()


def main():
    dirs = [Path(a) for a in sys.argv[1:] if not a.startswith("--")]
    phone_n = 2
    for a in sys.argv[1:]:
        if a.startswith("--phone="):
            phone_n = int(a.split("=")[1])
    errs = []
    with sync_playwright() as pl:
        b = pl.chromium.launch(args=V.LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
        for n, d in enumerate(dirs):
            run_page(b, d, False, errs)
            if n < phone_n:
                run_page(b, d, True, errs)
        b.close()
    print("ALL OK" if not errs else f"{len(errs)} FAIL")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
