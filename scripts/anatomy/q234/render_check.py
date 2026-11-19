#!/usr/bin/env python3
"""Q234: headless Chromium (swiftshader) renders of a built OWN page (three.js template): the chest with skin (faint), ribs / sternum / clavicle, pectoralis major + minor and the Q234 breast structures; anterior view and a
sagittal cut through the nipple (left / right), plus the pelvis with the vagina and ligaments (anterior, sagittal).
    python3 scripts/anatomy/q234/render_check.py THREE_MIN_JS PAGE_DIR HTML OUT_PREFIX"""
import base64, json, socket, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[3]
three, page_dir, html, prefix = sys.argv[1:5]
HOOK = ("var cutCtl = null, partsCtl = null, selCtl = null, capCtl = null;", "var cutCtl = null, partsCtl = null, selCtl = null, capCtl = null; window.__T = {meshes:meshes, scene:scene, camera:camera, renderer:renderer, root:root, THREE:THREE};")
JS = """(cfg) => {
  var T = window.__T, THREE = T.THREE, R = T.renderer, S = T.scene, root = T.root;
  var cols = cfg.colors, only = new Set(cfg.only);
  T.meshes.forEach(function(m){
    var u = m.userData || {}, id = (u.id || "").split("#")[0], sub = u.subject || "", cat = u.cat || "";
    var show = false, op = 1, col = null;
    if (id === "skin") { show = cfg.skin; op = cfg.skin_op; col = 0xd9a38a; }
    else if (cfg.ids.indexOf(id) >= 0 || (cfg.bones && cat === "bone" && cfg.bone_ids.indexOf(id) >= 0)) { show = true; op = (cat === "bone") ? 0.85 : 0.5; col = (cat === "bone") ? 0xe8e2d0 : 0xb03a3a; }
    if (sub.indexOf("xfer_hra") === 0 && sub.indexOf("_q234") > 0) { show = true; op = 1; col = cols[id] != null ? cols[id] : 0xc2549d; }
    if (sub === "xfer_hra2vhf_q233" && cfg.q233) { show = true; op = 0.9; col = 0x7a5fc2; }
    if (cfg.pelvis_ctx && ["urinary_bladder", "rectum"].indexOf(id) >= 0) { show = true; op = 0.35; col = id === "rectum" ? 0x8a6a3a : 0x3a8ad0; }
    if (only.size && !show) { /* nothing */ }
    m.visible = show;
    if (show) { m.material.opacity = op; m.material.transparent = op < 1; m.material.depthWrite = op >= 1; if (col != null) m.material.color.setHex(col); m.material.needsUpdate = true; }
  });
  R.localClippingEnabled = false; R.clippingPlanes = [];
  var c = cfg.center, h = cfg.half, W = R.domElement.width, H = R.domElement.height, asp = W / H;
  var cam = new THREE.OrthographicCamera(-h * asp, h * asp, h, -h, 1, 20000);
  var tw = root.localToWorld(new THREE.Vector3(c[0], c[1], c[2]));
  var d = cfg.dir, up = cfg.up;
  cam.position.set(tw.x + d[0] * 3000, tw.y + d[1] * 3000, tw.z + d[2] * 3000); cam.up.set(up[0], up[1], up[2]); cam.lookAt(tw);
  if (cfg.cut != null) { var pw = root.localToWorld(new THREE.Vector3(cfg.cut, 0, 0)); R.clippingPlanes = [new THREE.Plane(new THREE.Vector3(-d[0], 0, 0), d[0] * pw.x)]; }
  R.setClearColor(0xffffff, 1); R.render(S, cam);
  return R.domElement.toDataURL("image/png");
}"""
CFG_BASE = dict(skin=True, skin_op=0.10, bones=True, bone_ids=["ribs_l", "ribs_r", "sternum", "clavicle_l", "clavicle_r", "scapula_l", "scapula_r", "hip_bone_l", "hip_bone_r", "sacrum", "coccyx"],
                ids=["pectoralis_major_l", "pectoralis_major_r", "pectoralis_minor_l", "pectoralis_minor_r"], only=["x"], q233=False, pelvis_ctx=False, cut=None, half=170)
COL = {"breast_fat_l": 0xf2d16b, "breast_fat_r": 0xf2d16b, "mammary_gland_l": 0xd8548b, "mammary_gland_r": 0xd8548b, "lactiferous_ducts_l": 0x2fa86b, "lactiferous_ducts_r": 0x2fa86b,
       "areola_l": 0x8a4b2a, "areola_r": 0x8a4b2a, "nipple_l": 0x5a2a12, "nipple_r": 0x5a2a12, "breast_suspensory_ligaments_l": 0x2a6fd8, "breast_suspensory_ligaments_r": 0x2a6fd8, "vagina": 0xc2549d}
views = {}
for tag, nip in (("l", (-111, 377, 100)), ("r", (111, 377, 100))):
    views["breast_" + tag + "_front"] = dict(center=[nip[0] * 0.6, 440, 60], half=130, dir=[0, 0, 1], up=[0, 1, 0], ids=CFG_BASE["ids"])
    views["breast_" + tag + "_sagittal"] = dict(center=[nip[0], 420, 40], half=110, dir=[1 if tag == "l" else -1, 0, 0], up=[0, 1, 0], cut=nip[0], skin_op=0.18)
views["breast_both_front"] = dict(center=[0, 440, 60], half=270, dir=[0, 0, 1], up=[0, 1, 0])
views["pelvis_front"] = dict(center=[0, 40, 0], half=110, dir=[0, 0, 1], up=[0, 1, 0], q233=True, pelvis_ctx=True, ids=[], bone_ids=["hip_bone_l", "hip_bone_r", "sacrum", "coccyx"], skin_op=0.06)
views["pelvis_sagittal"] = dict(center=[0, 40, 0], half=110, dir=[-1, 0, 0], up=[0, 1, 0], q233=True, pelvis_ctx=True, ids=[], bone_ids=["hip_bone_l", "hip_bone_r", "sacrum", "coccyx"], cut=0.0, skin_op=0.06)
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
