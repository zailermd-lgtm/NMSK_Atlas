#!/usr/bin/env python3
"""Q249: headless Chromium (swiftshader, three.js) renders of a built page: the pelvic nerves in posterior, right-sagittal and inferior (perineal) views with bones, pelvic vessels and the muscles around them.
    python3 scripts/anatomy/q249/render_check.py THREE_MIN_JS PAGE_DIR HTML OUT_PREFIX KEY [--views posterior,sagittal,inferior]
Colours: sacral rami / lumbosacral trunk red, pudendal nerve + branches orange, gluteal / obturator internus / quadratus femoris / PFCN yellow, pelvic-floor motor + coccygeal teal, autonomic purple, medial branches blue,
abdominal green; existing page nerves (Z pudendal, sciatic ...) grey; arteries dark red, veins blue."""
import base64, json, re, socket, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[3]
a = [x for x in sys.argv[1:] if not x.startswith("--")]
three, page_dir, html, prefix, key = a[:5]
VIEWS = (sys.argv[sys.argv.index("--views") + 1].split(",") if "--views" in sys.argv else ["posterior", "sagittal", "inferior"])
HOOK = ("var cutCtl = null, partsCtl = null, selCtl = null, capCtl = null, labelsCtl = null;",
        "var cutCtl = null, partsCtl = null, selCtl = null, capCtl = null, labelsCtl = null; window.__T = {meshes:meshes, scene:scene, camera:camera, renderer:renderer, root:root, THREE:THREE};")
JS = """(cfg) => {
  var T = window.__T, THREE = T.THREE, R = T.renderer, S = T.scene, root = T.root;
  var newIds = new Set(cfg.new_ids), cnt = {nerves:0, bones:0, vessels:0, ctx:0};
  function grp(id){
    if (/^s[1-4]_ventral_ramus|^lumbosacral_trunk/.test(id)) return 0xd62828;
    if (/^(pudendal_n|inferior_rectal_n|perineal_n|dorsal_n_)/.test(id)) return 0xff8c00;
    if (/^(inferior_gluteal|nerve_to_obturator|nerve_to_quadratus|posterior_femoral)/.test(id)) return 0xe0b800;
    if (/^(nerve_to_levator|nerve_to_coccygeus|coccygeal_plexus|anococcygeal)/.test(id)) return 0x1f9d8f;
    if (/hypogastric|splanchnic/.test(id)) return 0x8e44ad;
    if (/medial_branch|dorsal_ramus/.test(id)) return 0x0077cc;
    if (/iliohypogastric|ilioinguinal|genitofemoral/.test(id)) return 0x5aa000;
    return 0xff00ff;
  }
  T.meshes.forEach(function(m){
    var u = m.userData || {}, id = (u.id || ""), base = id.split("#")[0], show = false, op = 1, col = null, kind = "";
    if (newIds.has(id)) { show = true; col = grp(id); op = 1; kind = "nerves"; }
    else if (cfg.bones.indexOf(base) >= 0) { show = true; op = 0.42; col = 0xe8e2d0; kind = "bones"; }
    else if (/^(zan_)?(internal_pudendal|inferior_gluteal|inferior_rectal)\\w*_(a|v|artery|vein|veins)(_[lr])?$/.test(base) || /^(internal_pudendal|inferior_rectal|middle_rectal)_v_[lr]$/.test(base)) { show = true; op = 0.75; col = /artery|_a_|_a$/.test(base) ? 0xa00020 : 0x2050c0; kind = "vessels"; }
    else if (cfg.nerves_existing.indexOf(base) >= 0 && !newIds.has(id)) { show = true; op = 0.7; col = 0x999999; kind = "ctx"; }
    else if (cfg.muscles.indexOf(base) >= 0) { show = true; op = 0.10; col = 0xb05a5a; kind = "ctx"; }
    if (cfg.hide_side === "l" && /_l$/.test(base)) show = false;
    if (cfg.hide_side === "r" && /_r$/.test(base)) show = false;
    if (cfg.hide_bone_side && /^hip_bone_/.test(base) && show) show = !(new RegExp("_" + cfg.hide_bone_side + "$").test(base));
    m.visible = show;
    if (show) { cnt[kind]++; m.material.opacity = op; m.material.transparent = op < 1; m.material.depthWrite = op >= 1; if (col != null) m.material.color.setHex(col); m.material.needsUpdate = true; }
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
shipped = json.loads((REPO / f"data/derived/Q249_shipped_{key}.json").read_text())
rj = json.loads((REPO / f"data/derived/Q249_rule_{key}.json").read_text())
L = rj["landmarks"]
c = [0.5 * (L["IS_l"][0] + L["IS_r"][0]), 0.5 * (L["IS_r"][1] + L["promontory"][1]) - 10, 0.5 * (L["IS_r"][2] + L["promontory"][2])]
BONES = ["hip_bone_l", "hip_bone_r", "sacrum", "coccyx", "sacrum#1", "sacrum#2"]
MUSC = ["piriformis_l", "piriformis_r", "obturator_internus_l", "obturator_internus_r", "levator_ani_l", "levator_ani_r", "coccygeus_l", "coccygeus_r", "external_anal_sphincter"]
EXIST = ["pudendal_n_l", "pudendal_n_r", "sciatic_n", "sciatic_n_l", "sciatic_n_r", "nerve_to_quadratus_femoris_l", "nerve_to_quadratus_femoris_r", "posterior_femoral_cutaneous_n_l", "posterior_femoral_cutaneous_n_r"]
BASE = dict(new_ids=list(shipped), bones=BONES, muscles=MUSC, nerves_existing=EXIST, hide_side=None, hide_bone_side=None)
views = {
    "posterior": dict(center=c, half=135, dir=[0, 0, -1], up=[0, 1, 0]),
    "sagittal": dict(center=[c[0] + 40, c[1], c[2]], half=150, dir=[1, 0, 0], up=[0, 1, 0], hide_side="l", hide_bone_side="l"),
    "inferior": dict(center=[c[0], c[1] - 30, c[2]], half=130, dir=[0, -1, 0], up=[0, 0, 1]),
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
        pg.wait_for_function("window.__T && window.__T.meshes && window.__T.meshes.length > 50", timeout=900000)
        time.sleep(4)
        for name in VIEWS:
            cfg = {**BASE, **views[name]}
            r = pg.evaluate(JS, cfg)
            Path(f"{prefix}_{name}.png").write_bytes(base64.b64decode(r["png"].split(",")[1])); counts[name] = r["counts"]
        b.close()
finally:
    srv.terminate()
print("page errors:", errs[:3], "visible:", counts)
