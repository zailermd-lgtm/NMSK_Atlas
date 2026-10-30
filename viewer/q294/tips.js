/* Q294: less text on screen.
   (1) Abbreviations: hovering (mouse) or tapping a short label -- a structure label drawn as its abbreviation (the labels module
       puts the full name in data-full), an <abbr title>, or anything carrying data-full -- opens a tiny popup with the full name.
       A tap still does what it did before (a label still selects its structure); the popup closes on the next tap or after 4 s.
   (2) Help text behind a small "i": static hint paragraphs of the panels (never a live status line, which stays visible) are
       folded behind an "i" button placed where the text was; tapping it shows / hides the text. New panels (built later by the
       optional add-ons) are folded too (a mutation observer, throttled). */
var NMSKTips = (function(){
  "use strict";
  var pop = null, popFor = null, popT = 0, started = false, moT = 0, folded = 0;
  var HINTS = "p.ss-hint, p.cp-hint, p.qv-hint, p.ln-hint, p.pp-hint, p.pp-help, p.ng-help, p.hint, p.mw-note, p.nmsk-tip, .us-help, .img-help";
  function fullOf(t){
    if (!t || !t.closest) return null;
    var e = t.closest("[data-full], abbr[title]");
    if (!e) return null;
    var f = e.getAttribute("data-full") || (e.tagName === "ABBR" ? e.getAttribute("title") : null);
    if (!f || f === (e.textContent || "").trim()) return null;
    return {el:e, text:f};
  }
  function show(info, x, y){
    if (!pop){ pop = document.createElement("div"); pop.id = "abbr-pop"; pop.className = "abbr-pop"; pop.setAttribute("role", "tooltip"); document.body.appendChild(pop); }
    pop.textContent = info.text; pop.hidden = false; popFor = info.el;
    var r = info.el.getBoundingClientRect ? info.el.getBoundingClientRect() : {left:x, right:x, top:y, bottom:y};
    var w = Math.min(280, window.innerWidth - 16);
    pop.style.maxWidth = w + "px";
    var pr = pop.getBoundingClientRect(), left = Math.max(8, Math.min(window.innerWidth - pr.width - 8, (r.left + r.right) / 2 - pr.width / 2)), top = r.top - pr.height - 6;
    if (top < 4) top = r.bottom + 6;
    pop.style.left = left + "px"; pop.style.top = top + "px";
    clearTimeout(popT); popT = setTimeout(hide, 4000);
  }
  function hide(){ if (pop){ pop.hidden = true; } popFor = null; }
  function fold(root){
    var l = (root || document).querySelectorAll(HINTS);
    for (var i = 0; i < l.length; i++){
      var p = l[i];
      if (p.getAttribute("data-tip") || p.hasAttribute("aria-live") || p.closest("[aria-live]") || p.closest(".no-tip")) continue;
      if (!(p.textContent || "").trim() && !p.id) continue;
      p.setAttribute("data-tip", "1"); p.classList.add("tip-txt");
      var b = document.createElement("button");
      b.type = "button"; b.className = "tip-i"; b.textContent = "i"; b.setAttribute("aria-expanded", "false"); b.setAttribute("aria-label", "Show the explanation"); b.title = "Show / hide the explanation";
      b.addEventListener("click", (function(pp, bb){ return function(e){ e.stopPropagation(); var o = !pp.classList.contains("tip-open"); pp.classList.toggle("tip-open", o); bb.setAttribute("aria-expanded", String(o)); }; })(p, b));
      p.parentNode.insertBefore(b, p);
      folded++;
    }
  }
  function start(){
    if (started) return; started = true;
    document.addEventListener("pointerover", function(e){ if (e.pointerType !== "mouse") return; var f = fullOf(e.target); if (f) show(f, e.clientX, e.clientY); }, true);
    document.addEventListener("pointerout", function(e){ if (e.pointerType !== "mouse" || !popFor) return; if (!e.relatedTarget || !popFor.contains(e.relatedTarget)) { var f = fullOf(e.target); if (f && f.el === popFor) hide(); } }, true);
    document.addEventListener("click", function(e){ var f = fullOf(e.target); if (f){ show(f, e.clientX, e.clientY); } else if (pop && !pop.hidden && e.target !== pop) hide(); }, true);
    fold(document);
    if (window.MutationObserver) new MutationObserver(function(){ if (!moT) moT = setTimeout(function(){ moT = 0; fold(document); }, 400); }).observe(document.body, {childList:true, subtree:true});
  }
  return {start:start, fold:fold, show:show, hide:hide, state:function(){ return {open:!!(pop && !pop.hidden), text:pop && !pop.hidden ? pop.textContent : null, folded:folded}; }};
})();
