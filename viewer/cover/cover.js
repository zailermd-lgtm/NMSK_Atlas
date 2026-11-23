/* Q389: an optional DISPLAY COVERING ("underwear") on the figure.  Owner: "allow the figures to wear underwear by choice" (so that
   results can be shown to children).
   It is NOT an anatomical structure and comes from no scan or atlas: the page's build step (scripts/anatomy/q389/make_cover_q389.py)
   derives it from the page's own skin mesh and writes it into the #nmsk-cover block --
     bound vertices   a point of ONE skin triangle (source piece k, vertices a b c, weights wa wb) lifted along the skin's normal by h.
                      They are recomputed here from the skin's current vertices and normals, so the covering follows the pose with
                      the skin's own weights; nothing of it is skinned separately.
     fixed vertices   the pouch: a second layer over the shell where it covers the external genital skin (a rounded hull of those skin
                      pieces, so that their shape does not read through). The pelvis is the root of the pose rig and does not move, so
                      these are constants; the shell under the pouch is bound like the rest and keeps the skin covered in a pose.
   What it does and does not do (decided in Q389, and said on the control):
     - off by default; "Briefs" on both bodies, a band "Top" as well where the page carries one (Base Female);
     - it is DRAWN only.  It is not in the picking / label / depth passes, so a click, a label, a measurement, the cut face and a
       planned needle all act on the anatomy under it exactly as if it were not there (a pick passes through it);
     - it takes the cut plane and the isolation box like everything else, stays opaque whatever the skin's own opacity, and stays on
       while the skin is peeled or hidden (what lies under it stays covered; switch it off to dissect the region);
     - the choice is an Undo step, part of a saved view, and remembered per page in this browser.
     NMSKCover.start(E)   E = engine adaptor {page, count, id(i), nverts(i), geo(i) -> {pos, nrm}, make(key, g), redraw()}
     .state()  .set({briefs, top})  .toggle(key)  .isOn(key)  .garment(key)  .refresh(key)  .compute(g, geo)  .decode(doc)  .ready() */
var NMSKCover = (function(){
  "use strict";
  var E = null, G = {}, ORDER = [], st = {}, ready = false, failed = "", KEY = "nmsk.cover.v1:", box = null, mounted = false, tries = 0, timer = 0, promise = null;
  function b64(s){ var bin = atob(s), u = new Uint8Array(bin.length); for (var i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return u; }
  function inflate(u8){
    if (typeof DecompressionStream === "undefined") return Promise.reject(new Error("this browser has no DecompressionStream"));
    return new Response(new Blob([u8]).stream().pipeThrough(new DecompressionStream("deflate"))).arrayBuffer();
  }
  function field(s, T){ return s ? inflate(b64(s)).then(function(b){ return new T(b); }) : Promise.resolve(new T(0)); }
  /* the page block -> typed arrays */
  function decode(doc){
    if (!doc || doc.schema !== "nmsk.cover.v1" || !doc.garments) return Promise.resolve(null);
    var keys = Object.keys(doc.garments).sort(function(a, b){ return a === "briefs" ? -1 : b === "briefs" ? 1 : a < b ? -1 : 1; });
    return Promise.all(keys.map(function(k){
      var g = doc.garments[k];
      return Promise.all([field(g.bind, Uint16Array), field(g.fix, Float32Array), field(g.body, Uint16Array), field(g.rim, Uint16Array)]).then(function(r){
        var o = {key:k, label:g.label || k, nb:g.nb | 0, nf:g.nf | 0, bind:r[0], fix:r[1], body:r[2], rim:r[3], band:g.band_mm || null};
        if (o.bind.length !== 7 * o.nb || o.fix.length !== 6 * o.nf) throw new Error("cover: garment " + k + " does not match its counts");
        o.n = o.nb + o.nf; o.pos = new Float32Array(3 * o.n); o.nrm = new Float32Array(3 * o.n);
        var used = {}, i; for (i = 0; i < o.nb; i++) used[o.bind[7 * i]] = 1;
        o.src = Object.keys(used).map(Number);
        return o;
      });
    })).then(function(list){ return {src:doc.src || [], garments:list, what:doc.what || ""}; });
  }
  /* positions and normals of one garment from the skin as it is now.  geo(k) -> {pos, nrm} of source piece k (Float32Array xyz) */
  function compute(g, geo){
    var B = g.bind, P = g.pos, N = g.nrm, cache = {}, v, o, k, s;
    for (v = 0; v < g.nb; v++){
      o = 7 * v; k = B[o]; s = cache[k] || (cache[k] = geo(k));
      var a = 3 * B[o + 1], b = 3 * B[o + 2], c = 3 * B[o + 3], wa = B[o + 4] / 65535, wb = B[o + 5] / 65535, wc = 1 - wa - wb, h = B[o + 6] / 100;
      var sp = s.pos, sn = s.nrm;
      var nx = wa * sn[a] + wb * sn[b] + wc * sn[c], ny = wa * sn[a + 1] + wb * sn[b + 1] + wc * sn[c + 1], nz = wa * sn[a + 2] + wb * sn[b + 2] + wc * sn[c + 2];
      var L = Math.sqrt(nx * nx + ny * ny + nz * nz) || 1; nx /= L; ny /= L; nz /= L;
      P[3 * v] = wa * sp[a] + wb * sp[b] + wc * sp[c] + h * nx;
      P[3 * v + 1] = wa * sp[a + 1] + wb * sp[b + 1] + wc * sp[c + 1] + h * ny;
      P[3 * v + 2] = wa * sp[a + 2] + wb * sp[b + 2] + wc * sp[c + 2] + h * nz;
      N[3 * v] = nx; N[3 * v + 1] = ny; N[3 * v + 2] = nz;
    }
    for (v = 0; v < g.nf; v++){
      o = 6 * v; k = 3 * (g.nb + v);
      P[k] = g.fix[o]; P[k + 1] = g.fix[o + 1]; P[k + 2] = g.fix[o + 2]; N[k] = g.fix[o + 3]; N[k + 1] = g.fix[o + 4]; N[k + 2] = g.fix[o + 5];
    }
    return g;
  }

  /* ---------------------------------------------------------------- state */
  function load(){ try { var s = localStorage.getItem(KEY + (E && E.page ? E.page : "page")); return s ? JSON.parse(s) : null; } catch (e){ return null; } }
  function save(){ try { localStorage.setItem(KEY + (E && E.page ? E.page : "page"), JSON.stringify(st)); } catch (e){} }
  function get(){ var o = {}; ORDER.forEach(function(k){ o[k] = !!st[k]; }); return o; }
  function apply(v, quiet){
    var ch = false;
    ORDER.forEach(function(k){ var w = !!(v && v[k]); if (w !== !!st[k]){ st[k] = w; ch = true; if (w && G[k]) G[k].dirty = true; } });
    if (ch){ if (!quiet) save(); paint(); if (E && E.redraw) E.redraw(); }
    return ch;
  }

  /* ---------------------------------------------------------------- the control and its section in the circled i */
  var WHAT = "A display covering, not an anatomical structure.";
  var NOTE = WHAT + " It is drawn over the skin from the skin's own surface and hides nothing from measurements: picking, labels, measuring, the cut and needle planning act on the anatomy under it.";
  function el(tag, cls, txt){ var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }
  function build(){
    if (box) return box;
    box = el("div", "cv-box"); box.id = "cv-box"; box.setAttribute("role", "group"); box.setAttribute("aria-label", "Underwear: a display covering, not an anatomical structure");
    var h = el("div", "cv-head"); h.appendChild(el("b", null, "Underwear"));
    var bd = el("span", "cv-badge", "display covering · not anatomy"); bd.id = "cv-badge"; bd.title = NOTE; h.appendChild(bd); box.appendChild(h);
    var rows = el("div", "cv-rows");
    ORDER.forEach(function(k){
      var l = el("label"), c = el("input"); c.type = "checkbox"; c.id = "cv-" + k; c.setAttribute("data-k", k);
      c.title = G[k].label + ": a display covering over the skin (not anatomy)";
      l.appendChild(c); l.appendChild(document.createTextNode(" " + G[k].label)); rows.appendChild(l);
    });
    box.appendChild(rows);
    var n = el("p", "cv-note", NOTE); n.id = "cv-note"; box.appendChild(n);
    box.addEventListener("change", function(e){
      var t = e.target, k = t && t.getAttribute ? t.getAttribute("data-k") : null; if (!k) return;
      var v = get(); v[k] = !!t.checked; apply(v);
      if (window.NMSKHistory && NMSKHistory.commit) NMSKHistory.commit();
    });
    return box;
  }
  function paint(){
    if (!box) return;
    ORDER.forEach(function(k){ var c = box.querySelector("#cv-" + k); if (c) c.checked = !!st[k]; });
    if (window.NMSKGroups && NMSKGroups.refresh){ try { NMSKGroups.refresh(); } catch (e){} }
  }
  function infoEl(){
    var d = el("div", "cv-info");
    d.innerHTML = "<p><b>" + WHAT + "</b> Off by default; switch it on under <b>Systems &rarr; Underwear</b> (" + ORDER.map(function(k){ return G[k].label; }).join(", ") + ").</p>" +
      "<p>It is made from this model's own skin surface at build time: the outer skin triangles inside a band, lifted a few millimetres along the skin's normal and kept taut, " +
      "and a smooth rounded hull over the external genital skin. The band's edges are a display convention of this viewer, not anatomy, and no scan or atlas is its source.</p>" +
      "<p>It is only drawn. A click passes through it to the structure under it, and labels, measurements, the cut face and needle planning use the anatomy as if it were not there. " +
      "It follows the pose with the skin, takes the cut plane, and stays on while the skin is faded, peeled or hidden. It is not a cloth simulation: in a large pose it can stretch or let the skin show at a fold.</p>";
    return d;
  }
  function mount(){
    if (mounted || !ready || !ORDER.length) return mounted;
    var Gp = window.NMSKGroups, I = window.NMSKInfo;
    if (!Gp || !Gp.addTo || !Gp.state || !Gp.state().on) return false;
    build();
    if (!Gp.addTo("systems", {el:box, active:function(){ return ORDER.some(function(k){ return !!st[k]; }); }})) return false;
    if (I && I.add) I.add({key:"cover", title:"Underwear: a display covering", order:46, el:infoEl()});
    mounted = true; paint();
    return true;
  }
  function boot(){ if (mount() || ++tries > 480){ clearInterval(timer); timer = 0; } }

  var api = {
    decode:decode, compute:compute,
    start:function(engine){
      if (promise) return promise;
      E = engine; var doc = null;
      try { var e = document.getElementById("nmsk-cover"); doc = e && e.textContent.trim().length > 2 ? JSON.parse(e.textContent) : null; } catch (err){ doc = null; }
      promise = decode(doc).then(function(d){
        if (!d || !d.garments.length) return false;
        /* the block was made for THIS geometry: every source piece must be the same structure with the same vertex count */
        var bad = 0; d.src.forEach(function(s){ if (!(s[0] < E.count) || E.id(s[0]) !== s[1] || E.nverts(s[0]) !== s[2]) bad++; });
        if (bad){ failed = "The display covering was made for another geometry (" + bad + " skin pieces differ). It is off."; if (window.console) console.warn("nmsk cover: " + failed); return false; }
        d.garments.forEach(function(g){
          g.srcIdx = g.src.map(function(k){ return d.src[k][0]; }); g.dirty = true;
          g.geo = function(k){ return E.geo(d.src[k][0]); };
          G[g.key] = g; ORDER.push(g.key); st[g.key] = false;
          if (E.make) E.make(g.key, g);
        });
        ready = true;
        var saved = load(); if (saved) apply(saved, true);
        if (window.NMSKHistory && NMSKHistory.register) NMSKHistory.register("cover", {get:get, set:function(v){ apply(v); }, reset:function(){ apply({}); }});
        boot(); if (!mounted) timer = setInterval(boot, 250);
        if (E.redraw) E.redraw();
        return true;
      }).catch(function(err){ failed = String(err && err.message || err); if (window.console) console.warn("nmsk cover: " + failed); return false; });
      return promise;
    },
    ready:function(){ return ready; },
    keys:function(){ return ORDER.slice(); },
    isOn:function(k){ return !!st[k]; },
    garment:function(k){ return G[k] || null; },
    /* the garment's arrays for the skin as it is now (recomputed only after the skin moved) */
    refresh:function(k){ var g = G[k]; if (!g) return null; if (g.dirty){ compute(g, g.geo); g.dirty = false; g.rev = (g.rev || 0) + 1; } return g; },
    /* the engine says which structures moved (indices); a garment whose skin pieces are among them is recomputed at the next draw */
    moved:function(ids){
      var any = false, set = null;
      ORDER.forEach(function(k){
        var g = G[k], i; if (g.dirty) return;
        if (!ids){ g.dirty = true; any = true; return; }
        if (!set){ set = {}; for (i = 0; i < ids.length; i++) set[ids[i]] = 1; }
        for (i = 0; i < g.srcIdx.length; i++) if (set[g.srcIdx[i]]){ g.dirty = true; any = true; break; }
      });
      return any;
    },
    set:function(v){ var o = get(), k; for (k in v) if (k in o) o[k] = !!v[k]; var ch = apply(o); if (ch && window.NMSKHistory && NMSKHistory.commit) NMSKHistory.commit(); return get(); },
    toggle:function(k){ var o = {}; o[k] = !st[k]; return api.set(o); },
    element:function(){ return ready ? build() : null; },
    state:function(){ return {ready:ready, failed:failed, mounted:mounted, on:get(), garments:ORDER.map(function(k){ var g = G[k]; return {key:k, label:g.label, bound:g.nb, pouch:g.nf, tris:(g.body.length + g.rim.length) / 3, pieces:g.srcIdx.length, band:g.band}; })}; }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKCover;
