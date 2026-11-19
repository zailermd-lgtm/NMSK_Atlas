/* Q318: named set-ups, kept in this browser.
   Owner: "a FAVORITES button as well, for keeping different preferred SETUPS (for example: a bones and
   insertions only state, a simulation of a needle going into the right pronator teres, and so on)."

   A favorite is exactly what the page already knows how to write down: ONE history snapshot -- every
   registered module's own get() -- under a name the owner gives it. Opening one goes back through
   history.restore(), the same path the model reset uses, so a module that joins the page later is
   carried without this file knowing anything about it, and nothing here duplicates another module's
   state.

   What a favorite does NOT hold is the viewpoint. The history leaves the camera out on purpose (a
   state you can undo into must not swing the model round under you), so a favorite restores what is
   shown and how, not where you were standing. That is said on the screen rather than quietly doing
   something else.

   They live in this browser only: no account, no server, and a different machine or a cleared site
   will not have them. Said on the screen too.

     NMSKFavorites.start({history})
     .element()  .list()  .save(name)  .open(name)  .remove(name)  .state() */
var NMSKFavorites = (function(){
  "use strict";
  var hist = null, box = null, listEl = null, nameEl = null, msgEl = null, on = false;
  var KEY = "nmsk.favorites.v1", MAX = 40, NAMEMAX = 60;

  function el(tag, cls, txt){ var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }
  /* every read and write is guarded: a private window, blocked site data or a full quota must leave the
     page working, with the reason on the screen, rather than throwing out of a click handler */
  function load(){
    try { var v = JSON.parse(window.localStorage.getItem(KEY) || "[]"); return v && v.length ? v : []; }
    catch (e){ return []; }
  }
  function store(L){
    try { window.localStorage.setItem(KEY, JSON.stringify(L)); return ""; }
    catch (e){ return "This browser would not keep it (private window, or no room left for site data)."; }
  }
  function say(m){ if (msgEl){ msgEl.textContent = m || ""; msgEl.hidden = !m; } }
  function when(t){
    try { return new Date(t).toLocaleDateString(undefined, {day:"numeric", month:"short"}); } catch (e){ return ""; }
  }

  function doSave(name){
    if (!hist || !hist.snapshot) return false;
    name = String(name == null ? "" : name).trim().slice(0, NAMEMAX);
    if (!name){ say("Give the set-up a name first."); return false; }
    var L = load(), i = -1, k;
    for (k = 0; k < L.length; k++) if (L[k].name === name) i = k;
    var rec = {name:name, at:Date.now(), snap:hist.snapshot()};
    if (i >= 0) L[i] = rec; else L.unshift(rec);
    if (L.length > MAX) L.length = MAX;
    var err = store(L);
    say(err || (i >= 0 ? "Replaced “" + name + "”." : "Saved “" + name + "”."));
    paint();
    return !err;
  }
  function doOpen(name){
    var L = load(), k;
    for (k = 0; k < L.length; k++) if (L[k].name === name){
      if (!hist || !hist.restore) return false;
      try { hist.restore(L[k].snap); } catch (e){ say("That set-up could not be opened."); return false; }
      if (hist.commit) hist.commit();              /* one undo step, so opening a favorite can be undone */
      say("Opened “" + name + "”. The viewpoint is not part of a set-up.");
      paint();
      return true;
    }
    return false;
  }
  function doRemove(name){
    var L = load().filter(function(r){ return r.name !== name; });
    var err = store(L);
    say(err || "Removed “" + name + "”.");
    paint();
    return !err;
  }

  function paint(){
    if (!listEl) return;
    var L = load();
    listEl.innerHTML = "";
    if (!L.length){
      listEl.appendChild(el("p", "fv-none", "No set-ups kept yet. Arrange the model as you want it, name it above, and save."));
      return;
    }
    L.forEach(function(r){
      var row = el("div", "fv-row");
      var b = el("button", "fv-open q301-b", r.name);
      b.type = "button";
      b.title = "Open this set-up (kept " + when(r.at) + ")";
      b.addEventListener("click", function(ev){ ev.stopPropagation(); doOpen(r.name); });
      var d = el("span", "fv-when", when(r.at));
      var x = el("button", "fv-x q301-b", "×");
      x.type = "button"; x.title = "Remove “" + r.name + "”";
      x.setAttribute("aria-label", "Remove " + r.name);
      x.addEventListener("click", function(ev){ ev.stopPropagation(); doRemove(r.name); });
      row.appendChild(b); row.appendChild(d); row.appendChild(x);
      listEl.appendChild(row);
    });
  }

  function build(){
    box = el("div", "fv-box");
    box.id = "fv-box";
    box.setAttribute("role", "group");
    box.setAttribute("aria-label", "Saved set-ups");

    var top = el("div", "fv-top");
    nameEl = el("input", "fv-name");
    nameEl.type = "text";
    nameEl.id = "fv-name";
    nameEl.placeholder = "Name this set-up";
    nameEl.maxLength = NAMEMAX;
    nameEl.setAttribute("aria-label", "A name for this set-up");
    nameEl.addEventListener("keydown", function(ev){ if (ev.key === "Enter"){ ev.preventDefault(); doSave(nameEl.value); nameEl.value = ""; } });
    var add = el("button", "fv-add q301-b", "Save this set-up");
    add.type = "button"; add.id = "fv-add";
    add.title = "Write down everything the model is showing now, under that name";
    add.addEventListener("click", function(ev){ ev.stopPropagation(); if (doSave(nameEl.value)) nameEl.value = ""; });
    top.appendChild(nameEl); top.appendChild(add);
    box.appendChild(top);

    msgEl = el("p", "fv-msg"); msgEl.hidden = true; msgEl.setAttribute("aria-live", "polite");
    box.appendChild(msgEl);

    listEl = el("div", "fv-list"); listEl.id = "fv-list";
    box.appendChild(listEl);

    box.appendChild(el("p", "fv-note", "A set-up keeps what is shown and how it is drawn — the systems, the layers, the cut, "
      + "the style, the pose, the needle. It does NOT keep the viewpoint, so opening one leaves you where you are. "
      + "They are kept in this browser only."));
    paint();
    return box;
  }

  var api = {
    start:function(opt){
      opt = opt || {};
      if (on) return api;
      hist = opt.history || window.NMSKHistory || null;
      if (!hist || !hist.snapshot || !hist.restore) return api;   /* without the history there is nothing to save */
      build();
      if (hist.onRegister) hist.onRegister(function(){ paint(); });
      on = true;
      return api;
    },
    element:function(){ return box; },
    list:function(){ return load().map(function(r){ return {name:r.name, at:r.at}; }); },
    save:function(name){ return doSave(name); },
    open:function(name){ return doOpen(name); },
    remove:function(name){ return doRemove(name); },
    refresh:paint,
    state:function(){ return {on:on, n:load().length}; }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKFavorites;
