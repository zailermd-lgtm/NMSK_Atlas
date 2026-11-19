/* Q343: the name card's group families and its Parts chooser (Base pages; data Q342, docs/Q342_groups_sources.md).
   Owner (translated): "one should be able to select groups of muscle fibres of the large muscles instead of the whole muscle
   -- by heads or divisions ... first ONE button 'Related structures'; clicking it opens the options. To those groups add a
   group of ANATOMY TRAINS -- vertical, horizontal, diagonal etc. Also a group by INNERVATION [root, peripheral, cerebral
   (e.g. flexor posture)], shown as a further menu."
   - "Myofascial lines" (order 40): class sheet (Vertical / Diagonal-spiral / Arm / Functional; Horizontal greyed with its
     reason) -> the lines of that class, those through the structure first, each with its evidence badge -> marks the
     line's muscle stations in station order on the structure's side (S = this side, O = the other, mid / B = both); the
     status line names the line and says its evidence plainly; "+ bones, fasciae, ligaments" adds the other stations.
   - "Innervation" (order 50): By root | By peripheral nerve | By central pattern, the structure's own first; a selected
     NERVE offers the muscles it supplies. Central patterns are rule-based (sourced posture + sourced muscle actions) and
     say so; their default marks the two tiers the source supports most directly, "All tiers" adds the rest.
   - Parts chooser (a card add-on): Whole muscle | each named part. Parts that are separate meshes select that mesh; the
     others are listed greyed with the reason; nothing rule-based is drawn. The card's Hide / Fade / Show only / Select then
     act on the chosen scope.
   Data: the page's sidecar groups_q342.json (scripts/anatomy/q342/build_sidecar_q342.py), fetched on the first card open.
   Marking goes through the selection controller (window.NMSKSelectCtl.markIds): one undo step per choice. */
var NMSKGroups342 = (function(){
  "use strict";
  var URL = "groups_q342.json", D = null, loading = null, failed = false, X = null, last = null;
  var EVS = {strong:"strong", moderate:"moderate", none:"no evidence", not_examined:"not examined"};
  var EVL = {strong:"Evidence: strong", moderate:"Evidence: moderate", none:"No dissection evidence — contested",
             not_examined:"Not examined by any review — contested"};
  var TOP = {named_in_guide:1, guide_section_and_action:1};
  function el(tag, cls, txt){ var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }
  function ctl(){ return window.NMSKSelectCtl || null; }
  function hist(){ try { var H = window.NMSKHistory; if (H && H.active && H.active()) H.commit(); } catch (err){} }
  function uniq(a){ var s = {}, o = []; a.forEach(function(x){ if (x && !s[x]){ s[x] = 1; o.push(x); } }); return o; }
  function sideOf(id){ return /_r$/.test(id) ? "r" : /_l$/.test(id) ? "l" : "mid"; }
  function other(s){ return s === "r" ? "l" : s === "l" ? "r" : "mid"; }
  function SN(s){ return s === "r" ? "right" : s === "l" ? "left" : "both sides"; }
  function get(o, ks){ var v = []; ks.forEach(function(k){ if (o && o[k]) v = v.concat(o[k]); }); return v; }
  /* the contract's side rule: the wanted sides, else mid, else both */
  function pick(o, ks){ var v = get(o, ks); if (!v.length) v = get(o, ["mid"]); if (!v.length) v = get(o, ["r", "l"]); return v; }
  function sides(s, both){ return both || s === "mid" ? ["r", "l", "mid"] : [s]; }

  function load(){
    if (D || failed || !window.fetch) return loading;
    if (loading) return loading;
    loading = fetch(URL).then(function(r){ if (!r.ok) throw new Error("no " + URL); return r.json(); }).then(function(j){
      if (!j || j.schema !== "nmsk.groups.page.v1") throw new Error("schema");
      D = j; index(); loading = null;
      try { var Q = window.NMSKQuick; if (Q && Q.relMenu && Q.relMenu()) Q.relOpen(); } catch (err){}
      return D;
    }).catch(function(){ failed = true; loading = null; return null; });
    return loading;
  }
  function index(){
    X = {mus:{}, nerve:{}, part:{}, line:[]};
    Object.keys(D.m).forEach(function(k){ get(D.m[k], ["r", "l", "mid"]).forEach(function(i){ (X.mus[i] = X.mus[i] || []).push(k); }); });
    Object.keys(D.inn.nerves).forEach(function(k){ get(D.inn.nerves[k], ["r", "l", "mid"]).forEach(function(i){ (X.nerve[i] = X.nerve[i] || []).push(k); }); });
    D.parts.forEach(function(mu){
      get(mu.whole, ["r", "l", "mid"]).forEach(function(i){ if (!X.part[i]) X.part[i] = {mu:mu, part:null}; });
      mu.p.forEach(function(p){ if (/^separate/.test(p.st)) get(p, ["r", "l", "mid"]).forEach(function(i){ X.part[i] = {mu:mu, part:p}; }); });
    });
    D.lines.items.forEach(function(L, n){ var s = {}; L.st.forEach(function(t){ get(t, ["r", "l", "mid"]).forEach(function(i){ s[i] = 1; }); }); X.line[n] = s; });
  }
  function name(m){ return D.m[m] ? D.m[m].n : m.replace(/_/g, " "); }
  function srcText(keys){
    return uniq(keys || []).map(function(k){ var s = D.src[k]; if (!s) return null;
      return s.l + (s.doi ? " (doi " + s.doi + ")" : s.pmid ? " (PMID " + s.pmid + ")" : ""); }).filter(Boolean).join("; ");
  }

  /* ---- the status line: one short line in the card (Q298's), extras after it, the method behind the (i) ---- */
  function say(text, more, extras){
    var Q = window.NMSKQ298;
    if (Q && Q.say) Q.say(text, more);
    var e = document.getElementById("q8-status"); if (!e) return;
    var ib = e.querySelector(".q8-i");
    (extras || []).forEach(function(x){
      var n;
      if (x.run){ n = el("button", "q8-b g3-x", x.label); n.type = "button"; n.addEventListener("click", function(ev){ ev.stopPropagation(); x.run(); }); }
      else { n = el("span", "g3-tag" + (x.cls ? " " + x.cls : ""), x.label); }
      if (x.key) n.setAttribute("data-g3", x.key);
      e.insertBefore(document.createTextNode(" "), ib || null); e.insertBefore(n, ib || null);
    });
  }
  function mark(ids, kind, key, side, extra){
    var c = ctl(); if (!c) return 0;
    ids = uniq(ids);
    var n = c.markIds(ids, true, true, true);
    hist();
    last = {kind:kind, key:key, side:side, ids:ids, marked:n, extra:extra || null};
    return n;
  }

  /* ---------------- Myofascial lines ---------------- */
  function linesOf(id){ var o = []; D.lines.items.forEach(function(L, n){ if (X.line[n][id]) o.push(L); }); return o; }
  function lineIds(L, side, all){
    var out = [];
    L.st.forEach(function(t){
      if (!all && t.k.indexOf("muscle") < 0) return;
      var ks = side === "mid" ? ["r", "l", "mid"] : t.s === "S" ? [side] : t.s === "O" ? [other(side)] : t.s === "mid" ? ["mid"] : ["r", "l", "mid"];
      out = out.concat(pick(t, ks));
    });
    return uniq(out);
  }
  function markLine(id, L, all){
    var s = sideOf(id), ids = lineIds(L, s, all), n = ids.length;
    mark(ids, "line", L.id, s, {all:!!all});
    var more = L.evt.charAt(0).toUpperCase() + L.evt.slice(1) + ". " + (L.how ? L.how + " " : "") +
      (L.book ? "Route as Myers describes it; the book itself was not opened, so the route is to be checked against it. " : "") +
      D.lines.contested + " Stations " + (all ? "marked: all (muscles, bones, fasciae, ligaments)" : "marked: the muscles; bones, fasciae and ligaments on request") +
      ", " + (L.x ? "crossing the midline where the line does" : "on the " + SN(s) + " (midline stations on both)") + ". Sources: " + srcText(L.refs) + ".";
    say((L.abbr ? L.abbr + " · " : "") + L.name + " · " + n + " marked", more,
        [{label:EVL[L.ev] || L.ev, cls:"g3-ev g3-ev-" + L.ev, key:"ev"},
         {label:all ? "Muscles only" : "+ bones, fasciae, ligaments", key:"all", run:function(){ markLine(id, L, !all); }}]);
  }
  function lineItem(id, L){
    return {label:(L.abbr ? L.abbr + " · " : "") + L.name, badge:EVS[L.ev] || L.ev, bcls:"g3-ev g3-ev-" + L.ev, here:!!X.line[D.lines.items.indexOf(L)][id],
            key:"line-" + L.id, title:L.evt, run:function(){ markLine(id, L, false); }};
  }
  function lineSheet(id, k){
    var mine = [], rest = [];
    D.lines.items.forEach(function(L, n){ if (L.cls.indexOf(k) < 0) return; (X.line[n][id] ? mine : rest).push(L); });
    var o = [];
    if (mine.length){ o.push({head:true, label:"Through this structure"}); mine.forEach(function(L){ o.push(lineItem(id, L)); }); }
    if (rest.length){ if (mine.length) o.push({head:true, label:"Other lines"}); rest.forEach(function(L){ o.push(lineItem(id, L)); }); }
    return o;
  }
  function lineFamily(id){
    if (!D){ load(); return failed ? [] : [{label:"Loading…", off:true, why:"The line data is still loading; open the menu again in a moment."}]; }
    var o = [{head:true, label:"Contested concept · evidence on each line"}];
    D.lines.cls.forEach(function(c){
      if (c.off){ o.push({label:c.label, off:true, why:c.why, key:"cls-" + c.k, badge:"none sourced"}); return; }
      var its = lineSheet(id, c.k), here = its.filter(function(x){ return x.here; }).length;
      o.push({label:c.label, key:"cls-" + c.k, items:its, n:its.filter(function(x){ return !x.head; }).length, here:here > 0, sheet:c.label});
    });
    return o;
  }

  /* ---------------- Innervation ---------------- */
  function musOf(id){ return (X.mus[id] || []).slice(); }
  function idsOfMuscles(ms, s, both){ var o = []; ms.forEach(function(m){ if (D.m[m]) o = o.concat(pick(D.m[m], sides(s, both))); }); return uniq(o); }
  function levelOf(lv){ var a = D.inn.levels.concat(D.inn.cranial); for (var i = 0; i < a.length; i++) if (a[i].lv === lv) return a[i]; return null; }
  function markRoot(id, lv, both){
    var L = levelOf(lv); if (!L) return;
    var s = sideOf(id), ids = idsOfMuscles(L.m, s, both), src = [];
    L.m.forEach(function(m){ src = src.concat(D.m[m].src || []); });
    mark(ids, "root", lv, both ? "both" : s, {both:!!both});
    var ex = [];
    if (L.key && L.key.m.length) ex.push({label:"Key muscle" + (L.key.m.length > 1 ? "s" : "") + " for " + lv + " (ISNCSCI): " + L.key.f + " — " +
                                          L.key.m.map(name).join(", "), cls:"g3-key", key:"key"});
    ex.push({label:both ? "This side only" : "Both sides", key:"both", run:function(){ markRoot(id, lv, !both); }});
    say(lv + " · " + L.m.length + " muscles marked" + (both || s === "mid" ? "" : " (" + SN(s) + ")"),
        D.inn.rules.root + " Muscles: " + L.m.map(function(m){ return name(m) + " (" + (D.m[m].rt || "") + ")"; }).join(", ") + ". Sources: " + srcText(src.concat(L.key ? ["isncsci2019"] : [])) + ".", ex);
  }
  function rootSheet(id, ms){
    var own = [];
    ms.forEach(function(m){ own = own.concat(D.m[m].lv || [], D.m[m].cn || []); });
    own = uniq(own);
    function it(L){ var k = L.key && L.key.m.some(function(m){ return ms.indexOf(m) >= 0; });
      return {label:L.lv, n:L.m.length, here:own.indexOf(L.lv) >= 0, key:"root-" + L.lv, badge:k ? "key muscle" : null,
              title:L.key ? "ISNCSCI key muscles for " + L.lv + ": " + L.key.f : null, run:function(){ markRoot(id, L.lv, false); }}; }
    var all = D.inn.levels.concat(D.inn.cranial), o = [];
    var mine = all.filter(function(L){ return own.indexOf(L.lv) >= 0; });
    if (mine.length){ o.push({head:true, label:"Roots of " + name(ms[0])}); mine.forEach(function(L){ o.push(it(L)); }); }
    o.push({head:true, label:"Other levels"});
    all.forEach(function(L){ if (own.indexOf(L.lv) < 0) o.push(it(L)); });
    return o;
  }
  function nerveIds(nid, s, both){
    var N = D.inn.nerves[nid], o = get(N, sides(s, both));
    N.m.forEach(function(x){ var V = x[1] && x[1] !== nid ? D.inn.nerves[x[1]] : null; if (V) o = o.concat(get(V, sides(s, both))); });
    return uniq(o);
  }
  function markNerve(id, nid, both){
    var N = D.inn.nerves[nid]; if (!N) return;
    var s = sideOf(id), ms = uniq(N.m.map(function(x){ return x[0]; })), nv = nerveIds(nid, s, both), ids = nv.concat(idsOfMuscles(ms, s, both));
    mark(ids, "nerve", nid, both ? "both" : s, {both:!!both, nerveMeshes:nv});
    say(N.n + " · " + ms.length + " muscles" + (nv.length ? " + the nerve" : "") + " marked" + (both || s === "mid" ? "" : " (" + SN(s) + ")"),
        D.inn.rules.nerve + (N.rt ? " Roots " + N.rt + "." : "") + " Muscles: " + ms.map(function(m){ var v = N.m.filter(function(x){ return x[0] === m; })[0];
          return name(m) + (v && v[1] && v[1] !== nid && D.inn.nerves[v[1]] ? " (via " + D.inn.nerves[v[1]].n + ")" : ""); }).join(", ") +
        (nv.length ? "" : ". This nerve has no mesh of its own on this body") + ". Source: " + srcText(["repo_registry"]) + ".",
        [{label:both ? "This side only" : "Both sides", key:"both", run:function(){ markNerve(id, nid, !both); }}]);
  }
  function nerveSheet(id, ms){
    var own = [];
    ms.forEach(function(m){ (D.m[m].nv || []).forEach(function(n){ var k = n, g = 0; while (k && D.inn.nerves[k] && g++ < 12){ own.push(k); k = D.inn.nerves[k].p; } }); });
    own = uniq(own).filter(function(n){ return D.inn.nerves[n] && D.inn.nerves[n].m.length; });
    function it(n, here){ var N = D.inn.nerves[n]; return {label:N.n, n:uniq(N.m.map(function(x){ return x[0]; })).length, here:here, key:"nerve-" + n, run:function(){ markNerve(id, n, false); }}; }
    var o = [];
    if (own.length){ o.push({head:true, label:"Nerve of " + name(ms[0])}); own.forEach(function(n){ o.push(it(n, true)); }); }
    o.push({head:true, label:"All nerves"});
    Object.keys(D.inn.nerves).filter(function(n){ return own.indexOf(n) < 0 && D.inn.nerves[n].m.length; })
      .sort(function(a, b){ return D.inn.nerves[a].n.localeCompare(D.inn.nerves[b].n); }).forEach(function(n){ o.push(it(n, false)); });
    return o;
  }
  function patOf(pid){ for (var i = 0; i < D.inn.pats.length; i++) if (D.inn.pats[i].id === pid) return D.inn.pats[i]; return null; }
  function markPat(id, P, all){
    var top = P.m.filter(function(x){ return TOP[x[1]]; }), use = all || !top.length ? P.m : top, s = sideOf(id);
    var ms = use.map(function(x){ return x[0]; }), ids = idsOfMuscles(ms, s, false);
    mark(ids, "central", P.id, s, {all:!!(all || !top.length), tiers:use.map(function(x){ return [x[0], x[1]]; })});
    var by = {};
    P.m.forEach(function(x){ (by[x[1]] = by[x[1]] || []).push(name(x[0]) + (x[2] ? " (its action opposes another component)" : "")); });
    var tiers = Object.keys(D.inn.tiers).filter(function(t){ return by[t]; }).map(function(t){ return D.inn.tiers[t] + ": " + by[t].join(", "); }).join(". ");
    var ex = [{label:"Rule-based from sourced posture + muscle actions", cls:"g3-rule", key:"rule"}];
    if (top.length && top.length < P.m.length) ex.push({label:all ? "Most direct tiers only" : "All tiers (+" + (P.m.length - top.length) + ")", key:"tiers", run:function(){ markPat(id, P, !all); }});
    say(P.n + " · " + ms.length + " muscles" + (use === P.m ? "" : " (most direct tiers)") + (s === "mid" ? "" : " · " + SN(s)),
        D.inn.rules.central + " Posture: " + P.comp.map(function(c){ return c[0] + (c[1] && D.src[c[1]] ? " (" + D.src[c[1]].l + ")" : ""); }).join("; ") +
        (P.miss.length ? ". Classic components not in the opened sources, not used: " + P.miss.join("; ") : "") + ". Tiers — " + tiers + ". Sources: " + srcText(P.refs) + ".", ex);
  }
  function patSheet(id, ms){
    var o = [{head:true, label:"Rule-based: sourced posture + muscle actions"}], mine = [], rest = [];
    D.inn.pats.forEach(function(P){ (P.m.some(function(x){ return ms.indexOf(x[0]) >= 0; }) ? mine : rest).push(P); });
    function it(P, here){ return {label:P.n, n:P.m.length, here:here, key:"pat-" + P.id, run:function(){ markPat(id, P, false); }}; }
    if (mine.length){ o.push({head:true, label:"Postures that include " + name(ms[0])}); mine.forEach(function(P){ o.push(it(P, true)); }); }
    if (rest.length){ o.push({head:true, label:mine.length ? "Other patterns" : "Patterns"}); rest.forEach(function(P){ o.push(it(P, false)); }); }
    return o;
  }
  function innFamily(id){
    if (!D){ load(); return failed ? [] : [{label:"Loading…", off:true, why:"The innervation data is still loading; open the menu again in a moment."}]; }
    var ms = musOf(id), o = [];
    if (ms.length){
      o.push({label:"By root", key:"root", items:rootSheet(id, ms), sheet:"By root"});
      o.push({label:"By peripheral nerve", key:"nerve", items:nerveSheet(id, ms), sheet:"By peripheral nerve"});
      o.push({label:"By central pattern", key:"central", items:patSheet(id, ms), sheet:"By central pattern"});
      return o;
    }
    (X.nerve[id] || []).forEach(function(n){
      var N = D.inn.nerves[n], k = uniq(N.m.map(function(x){ return x[0]; })).length;
      if (k) o.push({label:"Muscles it supplies" + ((X.nerve[id] || []).length > 1 ? " (" + N.n + ")" : ""), n:k, key:"sup-" + n, run:function(){ markNerve(id, n, false); }});
    });
    return o;
  }

  /* ---------------- Parts chooser (card add-on) ---------------- */
  function partInfo(id){ return X && X.part[id] ? X.part[id] : null; }
  function partsView(id, host, card){
    if (!D){ var p = load(); if (p) p.then(function(){ if (card.current() === id) card.redraw(); }); return; }
    var I = partInfo(id); if (!I) return;
    var mu = I.mu, s = sideOf(id), ks = s === "mid" ? ["r", "l", "mid"] : [s];
    var sep = mu.p.filter(function(p){ return /^separate/.test(p.st); });
    var whole = uniq(pick(mu.whole, ks).concat([].concat.apply([], sep.map(function(p){ return pick(p, ks); }))));
    var allMesh = uniq(get(mu.whole, ["r", "l", "mid"]).concat([].concat.apply([], sep.map(function(p){ return get(p, ["r", "l", "mid"]); }))));
    var hd = el("div", "g3-ph");
    hd.appendChild(document.createTextNode(I.part ? "Part of " : "Parts of ")); hd.appendChild(el("b", null, mu.n));
    if (I.part) hd.appendChild(document.createTextNode(" — this is the " + I.part.n.charAt(0).toLowerCase() + I.part.n.slice(1)));
    var row = el("div", "g3-prow"), note = el("p", "g3-pnote"); row.setAttribute("role", "group"); row.setAttribute("aria-label", "Parts of " + mu.n);
    note.setAttribute("aria-live", "polite");
    var bs = [];
    function chip(label, ids, part){
      var b = el("button", "g3-pc", label); b.type = "button"; b.setAttribute("data-part", part ? part.id : "whole");
      b.setAttribute("aria-pressed", "false"); bs.push(b);
      if (part && part.st === "separate_mesh_rule_based"){ b.appendChild(document.createTextNode(" ")); b.appendChild(el("span", "g3-rb", "rule-based")); b.title = part.why; }
      b.addEventListener("click", function(e){
        e.stopPropagation();
        var c = ctl(); if (!c) return;
        var keep = c.state().marks.filter(function(m){ return allMesh.indexOf(m) < 0; });
        c.markIds(keep.concat(ids), true, true, true);
        card.setScope(ids, label); hist();
        bs.forEach(function(x){ x.setAttribute("aria-pressed", String(x === b)); });
        note.textContent = (part ? part.n : "Whole " + mu.n.charAt(0).toLowerCase() + mu.n.slice(1)) + " selected (" + ids.length + " mesh" + (ids.length > 1 ? "es" : "") + ")" +
          (part && part.nerve ? " · " + part.nerve : "") + ". Hide, Fade, Show only and Select now act on it.";
        last = {kind:"part", key:part ? part.id : "whole", side:s, ids:ids.slice(), muscle:mu.id};
      });
      row.appendChild(b); return b;
    }
    var wb = chip("Whole muscle", whole, null);
    if (!I.part && whole.length === 1 && whole[0] === id) wb.setAttribute("aria-pressed", "true");
    mu.p.forEach(function(p){
      if (/^separate/.test(p.st)){
        var ids = pick(p, ks), b = chip(p.n, ids, p);
        if (I.part === p) b.setAttribute("aria-pressed", "true");
        return;
      }
      var g = el("button", "g3-pc g3-off", p.n); g.type = "button"; g.setAttribute("aria-disabled", "true"); g.setAttribute("data-part", p.id);
      g.title = p.n + ": " + p.why + (p.why2 ? " (" + p.why2 + ")" : "");
      g.addEventListener("click", function(e){ e.stopPropagation();
        note.textContent = p.n + ": " + p.why + (p.why2 ? " (" + p.why2 + ")" : "") + "." + (p.nerve ? " Nerve: " + p.nerve + "." : "") +
          (p.refs && p.refs.length ? " Source: " + srcText(p.refs) + "." : ""); });
      row.appendChild(g);
    });
    var off = mu.p.filter(function(p){ return !/^separate/.test(p.st); }).length;
    if (off) note.textContent = "Greyed: " + uniq(mu.p.filter(function(p){ return !/^separate/.test(p.st); }).map(function(p){ return p.why; })).join("; ") + " — tap one for details.";
    host.appendChild(hd); host.appendChild(row); host.appendChild(note);
  }

  function boot(){
    var Q = window.NMSKQuickCard; if (!Q || !Q.family) return false;
    Q.family({key:"mfl", label:"Myofascial lines", order:40, items:lineFamily, count:function(id){ return D ? linesOf(id).length : 0; }});
    Q.family({key:"inn", label:"Innervation", order:50, items:innFamily, count:function(){ return 0; }});   /* no number: its entries are kinds, not structures */
    if (Q.addon) Q.addon({key:"parts", order:10, render:partsView});
    return true;
  }
  boot();
  return {load:load, data:function(){ return D; }, lineIds:function(id, lid, all){ var L = D && D.lines.items.filter(function(x){ return x.id === lid; })[0]; return L ? lineIds(L, sideOf(id), all) : null; },
          state:function(){ return {loaded:!!D, failed:failed, last:last ? JSON.parse(JSON.stringify(last)) : null}; }};
})();
