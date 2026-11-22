/* Q344: layout and wording that the owner's audit found, kept out of the engine. Everything here is optional: a page without
   one of the elements simply skips it, and nothing writes anything but inline sizes and a class. */
(function(){
  "use strict";
  var PH = 700;
  function $(s, r){ return (r || document).querySelector(s); }
  function phone(){ return window.innerWidth <= PH; }
  function shown(e){
    if (!e || e.hidden) return false;
    var s = getComputedStyle(e); if (s.display === "none" || s.visibility === "hidden") return false;
    var r = e.getBoundingClientRect(); return r.width > 20 && r.height > 20;
  }

  /* the developer statistics line lives in the Sources box now */
  function stats(){
    var s = $("#stat-line"), sh = $("#modal .sheet");
    if (!s || !sh || !s.textContent.trim()) return;
    var p = $(".q344-stats", sh);
    if (!p){ p = document.createElement("p"); p.className = "q344-stats"; var h2 = $("h2", sh); if (h2 && h2.nextSibling) sh.insertBefore(p, h2.nextSibling); else sh.appendChild(p); }
    if (p.textContent !== s.textContent) p.textContent = s.textContent;
  }

  /* phone: Pose, Labels and the Layers rail open compact; the toggle in the panel opens them further */
  var PANELS = [
    {sel:"#pose-panel", head:".pz-head", open:function(e){ return shown(e); }},
    {sel:"#lab-panel", head:".lb-head", open:function(e){ return shown(e); }},
    {sel:"#rail", head:null, open:function(e){ return shown(e) && e.classList.contains("open"); }}
  ];
  function compact(){
    PANELS.forEach(function(P){
      var e = $(P.sel); if (!e) return;
      var on = P.open(e) && phone();
      if (!on){ if (e.hasAttribute("data-q344")){ e.removeAttribute("data-q344"); var t0 = $(".q344-tg", e); if (t0) t0.remove(); } return; }
      var tg = $(".q344-tg", e);
      if (!tg){
        tg = document.createElement("button"); tg.type = "button"; tg.className = "q344-tg";
        tg.addEventListener("click", function(ev){
          ev.stopPropagation();
          var c = e.getAttribute("data-q344") === "c";
          if (c) e.removeAttribute("data-q344"); else e.setAttribute("data-q344", "c");
          tg.textContent = c ? "Less" : "More"; tg.setAttribute("aria-expanded", String(c));
        });
        var h = P.head ? $(P.head, e) : null;
        if (h){ var x = h.lastElementChild; if (x && /close|^pz-x|×/.test((x.id || "") + (x.getAttribute("aria-label") || "") + x.textContent)) h.insertBefore(tg, x); else h.appendChild(tg); }
        else e.insertBefore(tg, e.firstChild);
        e.setAttribute("data-q344", "c"); tg.textContent = "More"; tg.setAttribute("aria-expanded", "false");
      }
    });
    /* the chips at the bottom edge ride above an open bottom panel instead of sitting on its controls */
    var lift = 0;
    if (phone()) PANELS.forEach(function(P){ var e = $(P.sel); if (e && P.open(e)){ var r = e.getBoundingClientRect(); if (r.bottom > window.innerHeight - 4) lift = Math.max(lift, Math.round(window.innerHeight - r.top)); } });
    document.body.classList.toggle("q344-lift", lift > 0);
    if (lift > 0) document.body.style.setProperty("--q344-lift", lift + "px"); else document.body.style.removeProperty("--q344-lift");
  }

  /* desktop: a panel does not start under the control bar */
  function clear(){
    if (phone()) return;
    var bar = $("#q301-bar"); if (!shown(bar)) return;
    var br = bar.getBoundingClientRect();
    ["#pose-panel", "#lab-panel"].forEach(function(sel){
      var e = $(sel); if (!shown(e)) return;
      var r = e.getBoundingClientRect();
      if (r.left < br.right - 4 && r.right > br.left + 4 && r.top < br.bottom + 2 && r.top > -1){
        var top = Math.round(br.bottom + 8);
        e.style.top = top + "px";
        e.style.maxHeight = Math.max(200, window.innerHeight - top - 14) + "px";
      }
    });
  }

  /* leaving Measure, or switching module, takes its pins and labels off the model */
  var lastMode = null;
  function modeWatch(){
    var m = document.body.classList.contains("mode-on");
    if (lastMode !== null && m !== lastMode){ try { if (window.NMSKMeasure && NMSKMeasure.ctl && NMSKMeasure.ctl.open) NMSKMeasure.ctl.open(false); } catch (e){} }
    lastMode = m;
  }

  /* a type floor for the panels that carry the owner's reading: nothing under 10 px */
  var ROOTS = "#info,#q301-sheet,#rail,#pose-panel,#lab-panel,#ms-bar,.qc,#sel-sec,#modal,#q8-float,#sa-bar,#pm-card,#pm-panel,#topright,#foot,#ref-root";
  function floor(){
    var roots = document.querySelectorAll(ROOTS), n = 0;
    for (var i = 0; i < roots.length; i++){
      var r = roots[i]; if (!shown(r) && r.id !== "modal") continue;
      var all = r.querySelectorAll("*");
      for (var j = 0; j < all.length && n < 4000; j++, n++){
        var e = all[j]; if (e.children.length > 0 && !e.firstChild) continue;
        if (!/\S/.test(e.textContent || "") || /^(SCRIPT|STYLE|SVG|PATH|CANVAS)$/i.test(e.tagName)) continue;
        var fs = parseFloat(getComputedStyle(e).fontSize);
        if (fs && fs < 10 && !e.hasAttribute("data-q344f")){ e.style.fontSize = "10.5px"; e.setAttribute("data-q344f", "1"); }
      }
    }
  }

  /* the card's mark button carries a check glyph that is transparent until pressed: it says "mark" instead */
  function markWord(){
    var m = document.getElementById("a-mark");
    if (m && m.textContent !== "mark" && m.textContent !== "marked ✓"){ m.textContent = "mark"; }
  }

  var busy = 0;
  function tick(){
    try { stats(); compact(); clear(); modeWatch(); markWord(); } catch (e){}
    if (!busy){ busy = setTimeout(function(){ busy = 0; try { floor(); } catch (e2){} }, 700); }
  }
  function start(){
    tick(); setInterval(tick, 500);
    window.addEventListener("resize", tick);
    document.addEventListener("click", function(){ setTimeout(tick, 60); }, true);
    var inf = document.getElementById("info");
    if (inf && window.MutationObserver) new MutationObserver(function(){ markWord(); }).observe(inf, {childList:true, subtree:true});
  }
  window.NMSKQ344 = {tick:tick, floor:floor};
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
