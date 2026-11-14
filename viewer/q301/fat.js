/* Q301: plain fat is OFF at load, and one tap away -- while the cut faces and the cross-sections stay filled.
   Owner: "plain fat in various places -- show it only when explicitly asked, not by default."
   Q295 added the fat / unlabelled-soft-tissue meshes from each body's OWN imaging -- 51 on every one of the six pages,
   17 of them labelled `Panniculus adiposus (tela subcutanea)`, i.e. the superficial fascia -- and shipped them ON at
   load but faint (alpha 0.12). (A page that happened to carry none would say so rather than pretend; the count is read
   off the page itself.) Two things change here and nothing else: the load default becomes OFF, and the cut face keeps
   drawing fat whatever the 3-D state is -- Q295's whole point was that a section must not read as hollow, and
   `NMSKCapCore.capA` already lifts fat to 0.9 in the cut face. No mesh is added or removed.
   The engine supplies E: {count(), shown(), set(on), redraw()}.
     NMSKFat.start(E, {toolbar, history, showall})
     .on()  .set(v)  .toggle()  .count()  .state() */
var NMSKFat = (function(){
  "use strict";
  var E = null, hist = null, box = null, btn = null, on = false, cur = false, touched = false, n = 0;
  function push(){
    if (!E || !E.set) return;
    try { E.set(cur); } catch (e){ if (window.console) console.error("fat", e); }
    if (E.redraw){ try { E.redraw(); } catch (e2){} }
  }
  function say(m){
    var e = document.getElementById("hist-msg");
    if (!e || !m) return;
    e.textContent = m; e.hidden = false;
    clearTimeout(say.t); say.t = setTimeout(function(){ e.hidden = true; }, 3000);
  }
  function ui(){
    if (!btn) return;
    btn.setAttribute("aria-pressed", String(cur));
    btn.classList.toggle("on", cur);
    btn.textContent = n ? (cur ? "Fat: shown" : "Fat: hidden") : "Fat: none on this page";
    btn.disabled = !n;
    btn.title = n ? (cur ? "Hide the " + n + " fat / unlabelled-soft-tissue structures again (they keep filling the cut faces)"
                         : "Show the " + n + " fat / unlabelled-soft-tissue structures (off at load, as asked)")
                  : "This page carries no fat mesh, so there is nothing to show or hide";
  }
  function set(v, quiet){
    v = !!v && n > 0;
    if (v === cur){ ui(); return false; }
    cur = v; touched = true; push(); ui();
    if (!quiet){
      if (hist && hist.schedule) hist.schedule();
      say(cur ? "Fat is shown, faint, as Q295 drew it. It fills the cut faces and the cross-sections either way."
              : "Fat is hidden again. It still fills the cut faces and the cross-sections, so a section never reads as hollow.");
      if (window.NMSKShowAll && NMSKShowAll.refresh) NMSKShowAll.refresh();
    }
    return true;
  }
  var api = {
    start:function(eng, opt){
      opt = opt || {};
      if (on) return api;
      E = eng || null; if (!E || typeof E.set !== "function") return api;
      hist = opt.history || window.NMSKHistory || null;
      try { n = E.count ? E.count() | 0 : 0; } catch (e){ n = 0; }
      cur = false; push();                              /* the load default: OFF, and it is applied, not merely declared */
      box = document.createElement("span");
      box.id = "ft-box"; box.className = "ft-box";
      btn = document.createElement("button");
      btn.type = "button"; btn.className = "ft-b q301-b"; btn.id = "ft-toggle";
      btn.addEventListener("click", function(e){ e.stopPropagation(); set(!cur); });
      box.appendChild(btn);
      var note = document.createElement("span"); note.className = "ft-note";
      note.innerHTML = '<p class="nmsk-tip">Fat and unlabelled soft tissue (Q295) is built from each body\'s own imaging in the space no segmented structure covers. ' +
        'It is <b>off at load</b>, as asked, and one tap shows it. Either way it <b>keeps filling the cut faces and the cross-sections</b>, ' +
        'because a section drawn without it reads as hollow &mdash; which was the whole reason Q295 built it. ' +
        (n ? "This page carries <b>" + n + "</b> such structures; the subcutaneous ones are labelled <i>Panniculus adiposus (tela subcutanea)</i> &mdash; the superficial fascia." : "<b>This page carries none.</b>") + '</p>';
      box.appendChild(note);
      if (opt.toolbar) opt.toolbar.appendChild(box); else document.body.appendChild(box);
      if (hist && hist.register) hist.register("fat", {get:function(){ return cur; }, set:function(v){ set(v, true); }, reset:function(){ set(false, true); }});
      if (opt.showall && opt.showall.add) opt.showall.add(api.source());
      on = true; ui();
      return api;
    },
    /* a hiding path only ONCE the user has used the control: at load "off" is the default, and Q300's rule is zero chrome then */
    source:function(){
      return {key:"fat", label:function(){ return "fat hidden"; },
        active:function(){ return on && n > 0 && touched && !cur; },
        clear:function(){ set(true, true); }, drive:function(){ set(true, true); touched = true; set(false, true); }};
    },
    on:function(){ return cur; }, set:function(v){ return set(v); }, toggle:function(){ return set(!cur); },
    count:function(){ return n; }, touched:function(){ return touched; }, refresh:ui,
    state:function(){ return {on:on, shown:cur, count:n, touched:touched}; }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKFat;
