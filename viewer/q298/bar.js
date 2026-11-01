/* Q298: the one row of controls under the search box. Progressive disclosure, phone first: nothing is shown until it has
   something to do. It carries, in this order, only when relevant:
     the result count and "Mark all N"                 (a search is running and matched something)
     a group chip per matching group, "Mark the group" (the query named a textbook group: "hamstrings", "rotator cuff")
     the three expansions of the selected structure    (a structure is selected)
     "Add by tapping the model"                        (always; it drives the engine's existing Mark-mode button)
     a note row                                        (the query named something the project cites but ships no mesh for)
   It is created in JS and inserted after the engine's own search box, so neither engine's layout had to be rebuilt. */
function NMSKQ298Bar(E, D, H){
  "use strict";
  var esc = H.esc, say = H.say;
  var root = document.createElement("div");
  root.className = "q8-bar";
  root.id = "q8-bar";
  root.innerHTML =
    '<div class="q8-row" id="q8-res" hidden>' +
      '<span class="q8-n" id="q8-count"></span>' +
      '<button type="button" class="q8-b" id="q8-all">Mark all</button>' +
      '<button type="button" class="q8-b" id="q8-range" aria-pressed="false" title="Mark a run of rows: tap the first, then the last (Shift-click on a desktop does the same)">Range</button>' +
      '<button type="button" class="q8-b" id="q8-onmodel" aria-pressed="false" title="While on, a tap or click on the model adds that structure to the marked set (Shift / Ctrl-click and a long press already do this at any time)">On model</button>' +
    '</div>' +
    '<div class="q8-row" id="q8-groups" hidden></div>' +
    '<div class="q8-row" id="q8-exp" hidden>' +
      '<span class="q8-n" id="q8-selname"></span>' +
      '<button type="button" class="q8-b" id="q8-adj">Adjacent</button>' +
      '<button type="button" class="q8-b" id="q8-rel">Related</button>' +
      '<button type="button" class="q8-b" id="q8-grp">Functional group</button>' +
    '</div>' +
    '<div class="q8-menu" id="q8-menu" hidden></div>' +
    '<p class="q8-note" id="q8-notes" hidden></p>' +
    '<p class="q8-status" id="q8-status" aria-live="polite"></p>';
  var box = E.box();
  if (box && box.parentNode) box.parentNode.insertBefore(root, box.nextSibling);
  else document.body.appendChild(root);

  var $ = function(id){ return document.getElementById(id); };
  var MULTI = null, EXP = null, lastRes = null, shown = [];

  function wire(m, x){
    MULTI = m; EXP = x;
    $("q8-all").addEventListener("click", function(){ MULTI.markAllResults(lastRes); });
    $("q8-range").addEventListener("click", function(){ MULTI.toggleRange(); });
    $("q8-onmodel").addEventListener("click", function(){ MULTI.toggleOnModel(); });
    $("q8-adj").addEventListener("click", function(){ EXP.run("adj"); });
    $("q8-rel").addEventListener("click", function(){ EXP.run("rel"); });
    $("q8-grp").addEventListener("click", function(){ EXP.run("grp"); });
    setInterval(function(){ selRow(); }, 700);          // the card can be opened from the model, not only from the list
  }

  function update(res, shownIds){
    lastRes = res; shown = shownIds || [];
    var n = res ? res.ids.length : 0, q = res ? res.q : "";
    var rb = $("q8-res");
    rb.hidden = !(q && n);
    if (!rb.hidden){
      $("q8-count").textContent = n === 1 ? "1 match" : n + " matches";
      $("q8-all").textContent = "Mark all " + n;
      $("q8-all").disabled = !E.sel();
    }
    var gb = $("q8-groups");
    var gs = res ? res.groups : [];
    gb.hidden = !gs.length;
    if (gs.length){
      gb.innerHTML = gs.map(function(g, i){
        return '<button type="button" class="q8-g" data-g="' + i + '" title="' + esc(g.why + (g.src ? " — " + g.src : "")) +
               '">' + esc(g.name) + ' <span class="q8-n">' + g.ids.length + '</span>' +
               (g.inferred ? ' <span class="q8-inf">inferred</span>' : "") + "</button>";
      }).join("");
      Array.prototype.forEach.call(gb.querySelectorAll("[data-g]"), function(b){
        b.addEventListener("click", function(){
          var g = gs[+b.getAttribute("data-g")];
          MULTI.markIds(g.ids, "the group " + g.name, g.src, g.inferred, g.why);
        });
      });
    }
    var nb = $("q8-notes");
    var ns = res ? res.notes : [];
    nb.hidden = !ns.length;
    if (ns.length){
      nb.innerHTML = ns.map(function(x){
        return "<b>" + esc(x.name) + "</b> — no mesh on this page. " + esc(x.why) +
               " This project's name for it: <i>" + esc(x.canon) + "</i>.";
      }).join("<br>");
    }
    selRow();
  }

  function selRow(){
    var eb = $("q8-exp"), id = E.selected();
    if (!id || !EXP){ eb.hidden = true; closeMenu(); return; }
    var c = EXP.counts(id);
    eb.hidden = false;
    $("q8-selname").textContent = EXP.nameOf(id);
    [["q8-adj", c.adj, "Adjacent"], ["q8-rel", c.rel, "Related"], ["q8-grp", c.grp, "Functional group"]]
      .forEach(function(t){
        var b = $(t[0]);
        b.textContent = t[2] + (t[1] ? " · " + t[1] : "");
        b.disabled = !t[1] || !E.sel();
      });
  }

  function menu(html, bind){
    var m = $("q8-menu");
    m.innerHTML = html; m.hidden = false;
    if (bind) bind(m);
  }
  function closeMenu(){ var m = $("q8-menu"); if (m){ m.hidden = true; m.innerHTML = ""; } }

  function pressed(id, v){ var b = $(id); if (b) b.setAttribute("aria-pressed", String(!!v)); }

  return {wire:wire, update:update, menu:menu, closeMenu:closeMenu, pressed:pressed, refresh:selRow,
          shown:function(){ return shown.slice(); }, root:root};
}
