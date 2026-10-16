#!/usr/bin/env python3
"""Q248: headless Chromium (swiftshader) renders of a built OWN page (three.js template): the pelvic floor from below (inferior view) and the right-side sagittal view, with the Q248 ligaments highlighted
(rule-based orange, Z-Anatomy transfers blue, CVH green) and the page's own organs / levator ani as context.  `--before` hides every Q248 structure (the same page without them, or the Q244 page).
    python3 scripts/anatomy/q248/render_check.py THREE_MIN_JS PAGE_DIR HTML OUT_PREFIX [--before] [--zoom]"""
import base64, json, socket, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[3]
a = [x for x in sys.argv[1:] if not x.startswith("--")]
three, page_dir, html, prefix = a[:4]
BEFORE = "--before" in sys.argv
HOOK = ("var cutCtl = null, partsCtl = null, selCtl = null, capCtl = null, labelsCtl = null;",
        "var cutCtl = null, partsCtl = null, selCtl = null, capCtl = null, labelsCtl = null; window.__T = {meshes:meshes, scene:scene, camera:camera, renderer:renderer, root:root, THREE:THREE};")
JS = """(cfg) => {
  var T = window.__T, THREE = T.THREE, R = T.renderer, S = T.scene, root = T.root;
  var ctx = new Set(cfg.context), bones = new Set(cfg.bones), cnt = {rule:0, xfer:0, cvh:0};
  T.meshes.forEach(function(m){
    var u = m.userData || {}, id = (u.id || "").split("#")[0], sub = u.subject || "";
    var show = false, op = 1, col = null;
    var q248 = /_q248$/.test(sub);
    if (id === "skin") { show = cfg.skin; op = cfg.skin_op; col = 0xd9a38a; }
    else if (bones.has(id)) { show = true; op = 0.55; col = 0xe8e2d0; }
    else if (ctx.has(id)) { show = true; op = /^(urinary_bladder|rectum|uterus|vagina|prostate)$/.test(id) ? 0.18 : 0.42; col = cfg.ctxcol[id] || 0x8a8a8a; }
    if (q248) {
      var kind = /rule/.test(sub) ? "rule" : (/cvh/.test(sub) ? "cvh" : "xfer");
      var pel = cfg.pelvic.indexOf(id.replace(/_(l|r)$/, "")) >= 0;
      show = !cfg.before && (cfg.all_new || pel); op = 1; col = kind === "rule" ? 0xe8742a : (kind === "cvh" ? 0x2aa84a : 0x2a56d8);
      if (show) cnt[kind]++;
    }
    if (cfg.hide_side === "l" && /_l$/.test(id)) show = false;
    if (cfg.hide_side === "r" && /_r$/.test(id)) show = false;
    m.visible = show;
    if (show) { m.material.opacity = op; m.material.transparent = op < 1; m.material.depthWrite = op >= 1; if (col != null) m.material.color.setHex(col); m.material.needsUpdate = true; }
  });
  R.localClippingEnabled = false; R.clippingPlanes = [];
  var c = cfg.center, h = cfg.half, W = R.domElement.width, H = R.domElement.height, asp = W / H;
  var cam = new THREE.OrthographicCamera(-h * asp, h * asp, h, -h, 1, 20000);
  var tw = root.localToWorld(new THREE.Vector3(c[0], c[1], c[2]));
  var d = cfg.dir, up = cfg.up;
  cam.position.set(tw.x + d[0] * 3000, tw.y + d[1] * 3000, tw.z + d[2] * 3000); cam.up.set(up[0], up[1], up[2]); cam.lookAt(tw);
  R.setClearColor(0xffffff, 1); R.render(S, cam);
  return {png: R.domElement.toDataURL("image/png"), counts: cnt};
}"""
PEL_BONES = ["hip_bone_l", "hip_bone_r", "sacrum", "coccyx"]
CTX = ["levator_ani_l", "levator_ani_r", "coccygeus_l", "coccygeus_r", "external_anal_sphincter", "obturator_internus_l", "obturator_internus_r"]
CTXCOL = {"urinary_bladder": 0x3a8ad0, "rectum": 0x8a6a3a, "uterus": 0x7a5fc2, "vagina": 0xc2549d, "prostate": 0x3aa0a0, "levator_ani_l": 0xb05a5a, "levator_ani_r": 0xb05a5a, "coccygeus_l": 0xb05a5a, "coccygeus_r": 0xb05a5a,
          "external_anal_sphincter": 0x8a6a3a, "obturator_internus_l": 0xc08a6a, "obturator_internus_r": 0xc08a6a}
PELVIC = ["tendinous_arch_levator_ani", "arcus_tendineus_fasciae_pelvis", "transverse_perineal_ligament", "anococcygeal_ligament", "anococcygeal_ligament_cvh", "pubovesical_ligament", "puboprostatic_ligament", "pubovesical_ligament_cvh",
          "sacrospinous_ligament", "sacrotuberous_ligament", "iliolumbar_ligament", "zan_anterior_sacro_iliac_ligament", "zan_posterior_sacro_iliac_ligament", "zan_interosseous_sacro_iliac_ligament", "obturator_membrane",
          "zan_obturator_membrane", "inguinal_ligament", "zan_inguinal_ligament", "arcuate_pubic_ligament", "superior_pubic_ligament", "zan_sacrococcygeal_symphysis"]
BASE = dict(skin=True, skin_op=0.04, bones=PEL_BONES, context=CTX, ctxcol=CTXCOL, pelvic=PELVIC, all_new=False, before=BEFORE, hide_side=None)
views = {
    "pelvic_floor_inferior": dict(center=[0, -20, -15], half=125, dir=[0, -1, 0], up=[0, 0, 1]),
    "pelvic_floor_sagittal_right": dict(center=[0, -10, -10], half=150, dir=[1, 0, 0], up=[0, 1, 0], hide_side="l"),
}
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", str(REPO / page_dir)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
errs, counts = [], {}
try:
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"], executable_path="/opt/pw-browsers/chromium")
        ctx = b.new_context(viewport=dict(width=1100, height=1000))
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))

        def route(rq):
            u = rq.request.url
            if "three" in u and u.endswith(".js") and ("cdnjs" in u or "jsdelivr" in u or "unpkg" in u):
                rq.fulfill(body=open(three, "rb").read(), content_type="application/javascript")
            elif "fonts.g" in u:
                rq.abort()
            else:
                rq.continue_()
        pg.route("**/*", route)

        def patch(rq):
            resp = rq.fetch(); t = resp.text()
            if HOOK[0] in t:
                t = t.replace(HOOK[0], HOOK[1], 1)
            rq.fulfill(response=resp, body=t)
        pg.route("**/*.html", patch)
        pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load")
        pg.wait_for_function("window.__T && window.__T.meshes && window.__T.meshes.length > 50", timeout=120000)
        time.sleep(3)
        for name, v in views.items():
            cfg = {**BASE, **v}
            r = pg.evaluate(JS, cfg)
            Path(f"{prefix}_{name}.png").write_bytes(base64.b64decode(r["png"].split(",")[1])); counts[name] = r["counts"]
        b.close()
finally:
    srv.terminate()
print("page errors:", errs[:3], "highlighted:", counts)
