#!/usr/bin/env python3
"""Q243: headless Chromium (swiftshader) renders of a built OWN page (three.js template): the pelvis with the HRA pelvic vessels (anterior view; right-side sagittal view with the left-sided structures hidden), the spine in
the midsagittal plane (clipped at x = 0: vertebrae, discs, nucleus pulposus, spinal cord segments) and a lumbar close-up. Arteries red, veins blue, nucleus pulposus gold, cord segments orange.
    python3 scripts/anatomy/q243/render_check.py THREE_MIN_JS PAGE_DIR HTML OUT_PREFIX"""
import base64, json, socket, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[3]
three, page_dir, html, prefix = sys.argv[1:5]
HOOK = ("var cutCtl = null, partsCtl = null, selCtl = null, capCtl = null, labelsCtl = null;",
        "var cutCtl = null, partsCtl = null, selCtl = null, capCtl = null, labelsCtl = null; window.__T = {meshes:meshes, scene:scene, camera:camera, renderer:renderer, root:root, THREE:THREE};")
JS = """(cfg) => {
  var T = window.__T, THREE = T.THREE, R = T.renderer, S = T.scene, root = T.root;
  var ctx = new Set(cfg.context), bones = new Set(cfg.bones);
  T.meshes.forEach(function(m){
    var u = m.userData || {}, id = (u.id || "").split("#")[0], sub = u.subject || "", cat = u.cat || "";
    var show = false, op = 1, col = null;
    var left = /_l$/.test(id), right = /_r$/.test(id);
    if (id === "skin") { show = cfg.skin; op = cfg.skin_op; col = 0xd9a38a; }
    else if (bones.has(id) || (cfg.vertebrae && /^(cervical|thoracic|lumbar)_vertebrae$/.test(id))) { show = true; op = 0.55; col = 0xe8e2d0; }
    else if (ctx.has(id)) { show = true; op = 0.30; col = cfg.ctxcol[id] || 0x8a8a8a; }
    else if (cfg.discs && /^intervertebral_disc_/.test(id)) { show = true; op = 0.35; col = 0x9a9aa8; }
    if (sub === "xfer_hra2vhf_q243") { show = true; op = 1; col = /_a(_l|_r)?$/.test(id) ? 0xd02828 : 0x2a56d8; }
    if (sub === "xfer_hra2vhf_spine_q243") {
      if (/^nucleus_pulposus_/.test(id)) { show = cfg.spine_items; op = 1; col = 0xf2b800; }
      else if (/^spinal_cord_segment_/.test(id)) { show = cfg.spine_items; op = 0.9; col = 0xe8742a; }
    }
    if (cfg.hide_side === "l" && left) show = false;
    if (cfg.hide_side === "r" && right) show = false;
    if (cfg.hide_vessels && sub === "xfer_hra2vhf_q243") show = false;
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
PEL_BONES = ["hip_bone_l", "hip_bone_r", "sacrum", "coccyx"]
CTX = ["urinary_bladder", "rectum", "uterus", "vagina", "uterine_tube_l", "uterine_tube_r"]
CTXCOL = {"urinary_bladder": 0x3a8ad0, "rectum": 0x8a6a3a, "uterus": 0x7a5fc2, "vagina": 0xc2549d, "uterine_tube_l": 0x7a5fc2, "uterine_tube_r": 0x7a5fc2}
BASE = dict(skin=True, skin_op=0.05, bones=PEL_BONES, context=CTX, ctxcol=CTXCOL, vertebrae=False, discs=False, spine_items=False, hide_side=None, hide_vessels=False, cut=None)
views = {
    "pelvis_front": dict(center=[0, 40, 0], half=115, dir=[0, 0, 1], up=[0, 1, 0]),
    "pelvis_sagittal_right": dict(center=[0, 40, 0], half=115, dir=[1, 0, 0], up=[0, 1, 0], hide_side="l"),
    "spine_sagittal": dict(center=[0, 400, -60], half=330, dir=[-1, 0, 0], up=[0, 1, 0], cut=0.0, bones=["sacrum", "coccyx"], context=[], vertebrae=True, discs=True, spine_items=True, skin_op=0.04, hide_vessels=True),
    "lumbar_sagittal": dict(center=[0, 210, -55], half=120, dir=[-1, 0, 0], up=[0, 1, 0], cut=0.0, bones=["sacrum", "coccyx"], context=[], vertebrae=True, discs=True, spine_items=True, skin=False, hide_vessels=True),
}
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", str(REPO / page_dir)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
errs = []
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
            png = pg.evaluate(JS, cfg)
            Path(f"{prefix}_{name}.png").write_bytes(base64.b64decode(png.split(",")[1]))
        b.close()
finally:
    srv.terminate()
print("page errors:", errs[:3])
