#!/usr/bin/env python3
"""Q234: headless Chromium (swiftshader) renders of a built Z page (WebGL template viewer/zan_atlas.template.html): anterior view of the chest (skin faint, bones, pectoralis major, the Q234 breast structures), a
sagittal cut through the left nipple (the page's own cut mode), and the pelvis with the vagina and ligaments (anterior, sagittal cut).
    python3 scripts/anatomy/q234/render_check_z.py PAGE_DIR HTML OUT_PREFIX [NIPPLE_X]"""
import json, socket, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[3]
page_dir, html, prefix = sys.argv[1:4]
HOOK = ('document.getElementById("btn-reset").onclick=resetAll;',
        'document.getElementById("btn-reset").onclick=resetAll; window.__Z = {OBJ:OBJ, hidden:hidden, faded:faded, on:on, alphaFor:alphaFor, getCam:function(){return cam;}, setCam:function(c){cam=c;}, need:function(){need=true;}, sync:function(){sync();}, cut:cutCtl, stop:function(){stopSpin();}};')
JS = """(cfg) => {
  var Z = window.__Z; Z.stop();
  var keep = new Set(cfg.keep_ids), q234 = new Set(cfg.new_ids), want = function(o){
    if (q234.has(o.id)) return true;
    if (o.layer === 'skin') return cfg.skin;
    if (o.layer === 'bone' && cfg.bone_re && new RegExp(cfg.bone_re).test(o.id)) return true;
    if (cfg.keep_re && new RegExp(cfg.keep_re).test(o.id)) return true;
    return false; };
  Z.hidden.clear(); Z.faded.clear();
  Z.OBJ.forEach(function(o){ var w = want(o); if (w && cfg.side && o.side && o.side !== 'm' && o.side !== cfg.side && !(o.layer === 'skin')) w = false; if (!w) Z.hidden.add(o); });
  Object.keys(Z.alphaFor).forEach(function(k){ Z.alphaFor[k] = 1; });
  Z.alphaFor.skin = cfg.skin_alpha; Z.alphaFor.muscle = 0.45; Z.alphaFor.bone = 0.9;
  Object.keys(Z.on).forEach(function(k){ Z.on[k] = true; });
  var c = Z.getCam(); c.az = cfg.az; c.el = cfg.el; c.dist = cfg.dist; c.tgt = cfg.tgt.slice(); Z.setCam(c);
  if (cfg.cut) Z.cut.setFromSpec({normal: cfg.cut.normal, point: cfg.cut.point}); else Z.cut.exit(true);
  Z.sync(); Z.need();
  var cp = document.getElementById('cut-panel'); if (cp) cp.style.display = 'none';
  var tr = document.getElementById('topright'); if (tr) tr.style.display = 'none';
  return Z.OBJ.filter(function(o){ return !Z.hidden.has(o); }).length;
}"""
rep = {}
p_rep = REPO / "data/derived" / ("Q234_report_%s.json" % ("comb_f" if "zan_female" in page_dir else "base_f"))
if p_rep.exists():
    rep = json.loads(p_rep.read_text())
added = [k for k, v in rep.get("structures", {}).items() if not v.get("held")]
breast_ids = [k for k in added if k.startswith(("breast_", "mammary_gland", "lactiferous", "areola", "nipple"))]
pelvic_ids = [k for k in added if k not in breast_ids]
nx = float(sys.argv[4]) if len(sys.argv) > 4 else -110.0
BONE = r"^(zan_.*rib|ribs|sternum|clavicle|scapula|zan_costal|zan_vertebra_t|hip_bone|sacrum|coccyx)"
views = {
    "chest_front": dict(new_ids=breast_ids, keep_re=r"pectoralis_major", bone_re=BONE, az=0, el=0, dist=700, tgt=[0, 440, 40], skin=True, skin_alpha=0.12),
    "chest_side_l": dict(new_ids=breast_ids, keep_re=r"pectoralis_major", bone_re=BONE, az=-1.5708, el=0, dist=600, tgt=[nx, 420, 40], skin=True, skin_alpha=0.15, side="l"),
    "chest_side_r": dict(new_ids=breast_ids, keep_re=r"pectoralis_major", bone_re=BONE, az=1.5708, el=0, dist=600, tgt=[-nx, 420, 40], skin=True, skin_alpha=0.15, side="r"),
    "chest_sagittal_l": dict(new_ids=breast_ids, keep_re=r"pectoralis_major", bone_re=BONE, az=-1.5708, el=0, dist=330, tgt=[nx, 410, 40], skin=True, skin_alpha=0.2, side="l", cut=dict(normal=[1, 0, 0], point=[nx, 0, 0])),
    "pelvis_front": dict(new_ids=pelvic_ids + ["uterus", "ovary_l", "ovary_r", "uterine_tube_l", "uterine_tube_r"], keep_re=r"(urinary_bladder|^rectum)", bone_re=BONE, az=0, el=0, dist=420, tgt=[0, 40, 0], skin=True, skin_alpha=0.06),
    "pelvis_sagittal": dict(new_ids=pelvic_ids + ["uterus", "ovary_l", "ovary_r", "uterine_tube_l", "uterine_tube_r"], keep_re=r"(urinary_bladder|^rectum)", bone_re=BONE, az=-1.5708, el=0, dist=420, tgt=[0, 40, 0], skin=True, skin_alpha=0.06, cut=dict(normal=[1, 0, 0], point=[0, 0, 0])),
}
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", str(REPO / page_dir)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
errs = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"], executable_path="/opt/pw-browsers/chromium")
        ctx = b.new_context(viewport=dict(width=900, height=1000))
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route("**/*", lambda rq: rq.abort() if "fonts.g" in rq.request.url else rq.continue_())
        def patch(rq):
            resp = rq.fetch(); t = resp.text()
            if HOOK[0] in t:
                t = t.replace(HOOK[0], HOOK[1], 1)
            rq.fulfill(response=resp, body=t)
        pg.route("**/*.html", patch)
        pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load")
        pg.wait_for_function("window.__Z && window.__Z.OBJ && window.__Z.OBJ.length > 100", timeout=90000)
        time.sleep(4)
        for name, v in views.items():
            cfg = dict(dict(keep_ids=[], bone_re=None, keep_re=None, side=None, cut=None, skin=True), **v)
            n = pg.evaluate(JS, cfg)
            time.sleep(2.5)
            pg.locator("#view").screenshot(path=f"{prefix}_{name}.png")
            print(name, "visible objects", n, flush=True)
        b.close()
finally:
    srv.terminate()
print("page errors:", errs[:3])
