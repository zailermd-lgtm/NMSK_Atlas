#!/usr/bin/env python3
"""Q235: headless Chromium (swiftshader) renders of a built OWN page (three.js template): the perineum from below (inferior view), the sagittal cut through the midline and the left side, and an anterior view of the pelvis with the
Q235 structures (Chinese Visible Human clitoris, vestibular bulbs, Bartholin's glands, perineal muscles, urethra layers / lumen, perineal body), the pelvic bones, bladder, rectum and the HRA vagina as context.
    python3 scripts/anatomy/q235/render_check.py THREE_MIN_JS PAGE_DIR HTML OUT_PREFIX"""
import base64, json, socket, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[3]
three, page_dir, html, prefix = sys.argv[1:5]
HOOK = ("var cutCtl = null, partsCtl = null, selCtl = null, capCtl = null;", "var cutCtl = null, partsCtl = null, selCtl = null, capCtl = null; window.__T = {meshes:meshes, scene:scene, camera:camera, renderer:renderer, root:root, THREE:THREE};")
JS = """(cfg) => {
  var T = window.__T, THREE = T.THREE, R = T.renderer, S = T.scene, root = T.root;
  var cols = cfg.colors;
  T.meshes.forEach(function(m){
    var u = m.userData || {}, id = (u.id || "").split("#")[0], sub = u.subject || "", cat = u.cat || "";
    var show = false, op = 1, col = null;
    if (id === "skin") { show = cfg.skin; op = cfg.skin_op; col = 0xd9a38a; }
    else if (cat === "bone" && cfg.bone_ids.indexOf(id) >= 0) { show = true; op = 0.55; col = 0xe8e2d0; }
    if (sub === "xfer_cvh2vhf_q235") { show = true; op = 1; col = cols[id.replace(/_(l|r)$/, "")] != null ? cols[id.replace(/_(l|r)$/, "")] : 0xc2549d; }
    if (id === "vagina" && sub.indexOf("_q234") > 0) { show = cfg.vagina; op = 0.28; col = 0xc2549d; }
    if (["urinary_bladder", "rectum"].indexOf(id) >= 0 && cfg.organs) { show = true; op = 0.22; col = id === "rectum" ? 0x8a6a3a : 0x3a8ad0; }
    if (cfg.own_muscles && ["bulbospongiosus_l", "bulbospongiosus_r", "ischiocavernosus_l", "ischiocavernosus_r", "deep_transverse_perineal_l", "deep_transverse_perineal_r", "external_anal_sphincter"].indexOf(id) >= 0 && sub.indexOf("pfloor") >= 0) { show = true; op = 0.3; col = 0x555555; }
    m.visible = show;
    if (show) { m.material.opacity = op; m.material.transparent = op < 1; m.material.depthWrite = op >= 1; if (col != null) m.material.color.setHex(col); m.material.needsUpdate = true; }
  });
  R.localClippingEnabled = false; R.clippingPlanes = [];
  var c = cfg.center, h = cfg.half, W = R.domElement.width, H = R.domElement.height, asp = W / H;
  var cam = new THREE.OrthographicCamera(-h * asp, h * asp, h, -h, 1, 20000);
  var tw = root.localToWorld(new THREE.Vector3(c[0], c[1], c[2]));
  var d = cfg.dir, up = cfg.up;
  cam.position.set(tw.x + d[0] * 3000, tw.y + d[1] * 3000, tw.z + d[2] * 3000); cam.up.set(up[0], up[1], up[2]); cam.lookAt(tw);
  if (cfg.cut != null) { var pw = root.localToWorld(new THREE.Vector3(cfg.cut, 0, 0)); R.clippingPlanes = [new THREE.Plane(new THREE.Vector3(-d[0], 0, 0), d[0] * pw.x)]; R.localClippingEnabled = true; T.meshes.forEach(function(m){ m.material.clippingPlanes = R.clippingPlanes; m.material.needsUpdate = true; }); }
  else { T.meshes.forEach(function(m){ m.material.clippingPlanes = null; m.material.needsUpdate = true; }); }
  R.setClearColor(0xffffff, 1); R.render(S, cam);
  return R.domElement.toDataURL("image/png");
}"""
CFG_BASE = dict(skin=False, skin_op=0.08, bone_ids=["hip_bone_l", "hip_bone_r", "sacrum", "coccyx"], vagina=True, organs=True, own_muscles=False, cut=None, half=70)
COL = {"clitoris_cavernous_body": 0xe02020, "vestibular_bulb": 0xff8c00, "bartholin_gland": 0x2040e0, "bulbospongiosus_cvh": 0x20a0a0, "ischiocavernosus_cvh": 0x8030c0, "superficial_transverse_perineal_cvh": 0xd020d0,
       "deep_perineal_muscle_cvh": 0x20b020, "urethral_sphincter_cvh": 0x00c0e0, "urethral_sphincter_raphe_cvh": 0x006080, "urethral_compressor_cvh": 0x40e0c0, "urethrovaginal_sphincter_cvh": 0x80e020,
       "urethra_female_submucous_layer": 0xf0e020, "urethra_female_lumen": 0x202020, "perineal_body": 0x602010}
views = {
    "perineum_inferior": dict(center=[0, -60, -10], half=62, dir=[0, -1, 0], up=[0, 0, 1], skin=False),
    "perineum_sagittal_midline": dict(center=[0, -30, -10], half=60, dir=[-1, 0, 0], up=[0, 1, 0], cut=0.0),
    "perineum_sagittal_left": dict(center=[-12, -30, -10], half=60, dir=[-1, 0, 0], up=[0, 1, 0], cut=-12.0, vagina=False),
    "perineum_front": dict(center=[0, -35, 0], half=70, dir=[0, 0, 1], up=[0, 1, 0]),
    "perineum_oblique": dict(center=[0, -45, 0], half=62, dir=[-0.55, -0.6, 0.6], up=[0, 1, 0]),
    "perineum_with_own_muscles_inferior": dict(center=[0, -60, -10], half=62, dir=[0, -1, 0], up=[0, 0, 1], own_muscles=True),
}
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", str(REPO / page_dir)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"], executable_path="/opt/pw-browsers/chromium")
        ctx = b.new_context(viewport=dict(width=1100, height=900))
        pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route("**/*", lambda rq: rq.fulfill(body=open(three, "rb").read(), content_type="application/javascript") if ("three" in rq.request.url and ("cdnjs" in rq.request.url or "jsdelivr" in rq.request.url or "unpkg" in rq.request.url))
                 else (rq.abort() if "fonts.g" in rq.request.url else rq.continue_()))
        def patch(rq):
            resp = rq.fetch(); t = resp.text()
            if HOOK[0] in t:
                t = t.replace(HOOK[0], HOOK[1], 1)
            rq.fulfill(response=resp, body=t)
        pg.route("**/*.html", patch)
        pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load")
        pg.wait_for_function("window.__T && window.__T.meshes && window.__T.meshes.length > 50", timeout=60000)
        time.sleep(3)
        for name, v in views.items():
            cfg = {**CFG_BASE, **v, "colors": COL}
            png = pg.evaluate(JS, cfg)
            Path(f"{prefix}_{name}.png").write_bytes(base64.b64decode(png.split(",")[1]))
        b.close()
finally:
    srv.terminate()
print("page errors:", errs[:3])
