/* Q298 search core: one matcher for both viewer engines, no DOM, so tests/test_q298.py can drive it through the page and
   scripts can reason about it.

   WHY THIS EXISTS. The owner looked for the iliotibial tract as "ITB" and as "iliotibial band" and the search returned
   nothing. Before this round each engine matched the query as ONE CONTIGUOUS SUBSTRING of ONE field -- the Z engine
   `o.name.toLowerCase().indexOf(q)`, the own engine the same over `name + " " + id` -- so:
     * no abbreviation could ever match (no page name contains the letters "itb");
     * a multi-word query failed unless those words were contiguous and in that order ("iliotibial band" misses
       "Iliotibial (IT) tract/band", which does contain both words);
     * the Latin / Terminologia name, the structure's group, its system and its part-of parent were never searched
       (the Z engine did not even search the id);
     * a single typo returned nothing;
     * and the results were ordered by the page's draw order (own) or alphabetically (Z), never by how well they matched.

   WHAT IT MATCHES, in this order of rank:
     5  an exact alias: the whole query is an abbreviation, synonym, Latin form, Hebrew name or eponym of a structure
        (data/anatomy/synonyms_q298.json, resolved to THIS page's structures at build time)
     4  an exact name: the query is the structure's own name (or its Latin name, or its id)
     3  a word start: a word of the name / Latin / id / group / system / part-of parent starts with the query
     2  a substring anywhere in those fields
     1  fuzzy: within 1 edit (queries of 5 characters or fewer) or 2 edits (longer) of a word of the name or of the
        whole name, and prefix aliases
   A sub-part (a head, a part, a "continuation beyond the data-block cut" piece, anything with a part-of parent) is
   ranked below a whole structure of the same score, which is the "prefer whole structures over sub-parts" rule.

   Everything is folded the same way the build step folds it: lower case, accents stripped, every run of punctuation or
   space to one space. Hebrew letters pass through unchanged, so a Hebrew query matches a Hebrew alias. */
var NMSKSearchCore = (function(){
  "use strict";
  var CJ = /[̀-ͯ]/g, PUNCT = /[^0-9a-z֐-׿]+/g;

  function fold(s){
    s = String(s == null ? "" : s).toLowerCase();
    try { s = s.normalize("NFKD").replace(CJ, ""); } catch (err){}
    return s.replace(PUNCT, " ").replace(/^ +| +$/g, "");
  }

  /* bounded Levenshtein: returns a number > max as soon as it cannot be <= max (cheap enough for 3,300 structures) */
  function dist(a, b, max){
    var la = a.length, lb = b.length;
    if (Math.abs(la - lb) > max) return max + 1;
    var prev = new Array(lb + 1), cur = new Array(lb + 1), i, j;
    for (j = 0; j <= lb; j++) prev[j] = j;
    for (i = 1; i <= la; i++){
      cur[0] = i;
      var lo = Math.max(1, i - max), hi = Math.min(lb, i + max), best = max + 1;
      for (j = 1; j <= lb; j++) cur[j] = max + 1;
      for (j = lo; j <= hi; j++){
        var c = a.charCodeAt(i - 1) === b.charCodeAt(j - 1) ? 0 : 1;
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + c);
        if (cur[j] < best) best = cur[j];
      }
      if (best > max) return max + 1;
      var t = prev; prev = cur; cur = t;
    }
    return prev[lb];
  }

  function build(cfg){
    var items = cfg.items || [], D = cfg.data || {}, i, k;
    var ids = D.ids || [], sub = D.sub || [], alias = D.alias || [], groups = D.groups || [], ns = D.ns || [];
    var subOf = {};                                                 // id -> 1 when the build step called it a sub-part
    for (i = 0; i < ids.length; i++) if (sub[i]) subOf[ids[i]] = 1;

    var rows = [];                                                  // one per list item, in the engine's own list order
    var byId = {};
    for (i = 0; i < items.length; i++){
      var it = items[i];
      var name = fold(it.name), latin = fold(it.latin), sid = fold(String(it.id).replace(/_/g, " "));
      var extra = fold([it.cat, it.part, it.group, it.note].join(" "));
      var hay = name + " | " + latin + " | " + sid + " | " + extra;
      var words = (name + " " + latin + " " + sid + " " + extra).split(" ");
      var seen = {}, w = [];
      for (k = 0; k < words.length; k++) if (words[k] && !seen[words[k]]){ seen[words[k]] = 1; w.push(words[k]); }
      rows.push({id:it.id, name:name, latin:latin, hay:hay, words:w,
                 sub:(subOf[it.id] || it.sub) ? 1 : 0});
      if (!(it.id in byId)) byId[it.id] = [];
      byId[it.id].push(rows.length - 1);
    }

    var aliasByQ = {};                                              // folded query form -> [alias]
    for (i = 0; i < alias.length; i++){
      var a = alias[i];
      if (!aliasByQ[a.q]) aliasByQ[a.q] = [];
      aliasByQ[a.q].push(a);
    }
    var aliasQ = Object.keys(aliasByQ).sort();

    function idsOfAlias(a){
      var out = [], j;
      for (j = 0; j < (a.i || []).length; j++){ var s = ids[a.i[j]]; if (s) out.push(s); }
      return out;
    }

    function run(q0){
      q0 = fold(q0);
      var out = {q:q0, ids:[], why:{}, score:{}, groups:[], notes:[], approx:0, approx_of:"",
                 note_first:0, stats:{exact:0, alias:0, wordstart:0, substr:0, fuzzy:0}};
      if (!q0){
        for (var z = 0; z < rows.length; z++) out.ids.push(rows[z].id);
        return out;
      }
      var score = {}, why = {}, j, n, id;

      function bump(sid, s, w){
        if (!(sid in score) || score[sid] < s){ score[sid] = s; if (w) why[sid] = w; }
        else if (score[sid] === s && w && !why[sid]) why[sid] = w;
      }

      /* 1. aliases: exact first, then a prefix of an alias (so "iliotib" reaches the band / tract synonyms too) */
      var al = aliasByQ[q0] || [];
      for (j = 0; j < al.length; j++){
        var lst = idsOfAlias(al[j]);
        for (n = 0; n < lst.length; n++) bump(lst[n], 5, al[j]);
        out.stats.alias += lst.length;
      }
      if (q0.length >= 2){
        for (j = 0; j < aliasQ.length; j++){
          if (aliasQ[j].length > q0.length && aliasQ[j].indexOf(q0) === 0){
            var pl = aliasByQ[aliasQ[j]];
            for (n = 0; n < pl.length; n++){
              var l2 = idsOfAlias(pl[n]);
              for (var m = 0; m < l2.length; m++) bump(l2[m], 2.5, pl[n]);
            }
          }
        }
      }

      /* 2. the page's own fields */
      for (j = 0; j < rows.length; j++){
        var r = rows[j], s = 0;
        if (r.name === q0 || r.latin === q0) s = 4;
        else {
          for (n = 0; n < r.words.length; n++) if (r.words[n].indexOf(q0) === 0){ s = 3; break; }
          if (!s && r.hay.indexOf(q0) >= 0) s = 2;
        }
        if (s){
          if (s === 4) out.stats.exact++; else if (s === 3) out.stats.wordstart++; else out.stats.substr++;
          bump(r.id, s, null);
        }
      }

      /* 3. fuzzy, ONLY when nothing else matched at all (a "did you mean", not an extra filter). Gating it this way is
            also what keeps a keystroke cheap: the edit-distance pass over 3,300 names and their words is the expensive
            part, and on a query that already matches something it never runs. */
      var found = 0; for (id in score) if (score.hasOwnProperty(id)) found++;
      if (q0.length >= 4 && found === 0){
        var max = q0.length <= 5 ? 1 : 2;
        for (j = 0; j < rows.length; j++){
          var r2 = rows[j];
          if (score[r2.id] >= 2) continue;
          var hit = dist(q0, r2.name, max) <= max;
          if (!hit) for (n = 0; n < r2.words.length && !hit; n++){
            if (r2.words[n].length >= 3 && dist(q0, r2.words[n], max) <= max) hit = true;
          }
          if (hit){ bump(r2.id, 1, null); out.stats.fuzzy++; }
        }
        for (j = 0; j < aliasQ.length; j++){
          if (dist(q0, aliasQ[j], max) <= max){
            var fl = aliasByQ[aliasQ[j]];
            for (n = 0; n < fl.length; n++){
              var l3 = idsOfAlias(fl[n]);
              for (var m3 = 0; m3 < l3.length; m3++) bump(l3[m3], 1.5, fl[n]);
            }
          }
        }
      }

      /* 4. rank: score, then whole structures before sub-parts, then by name */
      var pick = [];
      for (j = 0; j < rows.length; j++){
        var r3 = rows[j];
        if (!(r3.id in score)) continue;
        pick.push({id:r3.id, s:score[r3.id], sub:r3.sub, name:r3.name, ord:j});
      }
      var seen2 = {};
      pick.sort(function(a, b){
        return (b.s - a.s) || (a.sub - b.sub) || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0) || (a.ord - b.ord);
      });
      var best = 0;
      for (j = 0; j < pick.length; j++){
        if (seen2[pick[j].id]) continue;
        seen2[pick[j].id] = 1;
        out.ids.push(pick[j].id);
        out.score[pick[j].id] = pick[j].s;
        if (pick[j].s > best) best = pick[j].s;
        if (why[pick[j].id]) out.why[pick[j].id] = why[pick[j].id];
      }
      /* Q306: SAY SO when nothing actually matched and these are only near-misses. Before Q306 the fuzzy
         pass answered "psoas minor" with Psoas major and "long head of biceps brachii" with the long head
         of TRICEPS brachii, at rank 1, with no sign that the query had matched nothing -- the page stated
         something false with confidence. `approx` is set when every row came from the fuzzy pass, so the
         bar can print "no exact match for X -- closest names" above the rows, and `approx_of` carries the
         query the near-misses are near. */
      out.approx = (out.ids.length && best <= 1.5) ? 1 : 0;
      if (out.approx) out.approx_of = q0;

      /* 5. groups whose own name or alias matches -- offered as ONE selectable row each */
      for (j = 0; j < groups.length; j++){
        var g = groups[j], hit2 = fold(g.name).indexOf(q0) >= 0, n2;
        for (n2 = 0; n2 < (g.al || []).length && !hit2; n2++){
          if (g.al[n2] === q0 || (q0.length >= 2 && g.al[n2].indexOf(q0) === 0)) hit2 = true;
        }
        if (hit2){
          var gi = [];
          for (n2 = 0; n2 < (g.i || []).length; n2++){ var gs = ids[g.i[n2]]; if (gs) gi.push(gs); }
          if (gi.length) out.groups.push({id:g.id, name:g.name, src:g.src, inferred:g.inferred, why:g.why, ids:gi});
        }
      }

      /* 6. names this project cites but ships no mesh for (Colles' and Scarpa's fascia, Gerdy's tubercle, the pectineal
            ligament of Cooper): say so instead of returning nothing */
      for (j = 0; j < ns.length; j++){
        for (n = 0; n < (ns[j].q || []).length; n++){
          if (ns[j].q[n] === q0 || (q0.length >= 3 && ns[j].q[n].indexOf(q0) === 0)){
            out.notes.push(ns[j]);
            /* Q306: when the note matched the query EXACTLY and no structure did, the note is the answer
               and the structure rows are near-misses. "psoas minor" on a Z page used to return Psoas
               major at rank 1; now the explanation comes first and the rows are marked as approximate. */
            if (ns[j].q[n] === q0 && best < 4) out.note_first = 1;
            break;
          }
        }
      }
      if (out.note_first && out.ids.length) out.approx = 1;
      return out;
    }

    return {run:run, fold:fold, count:rows.length, aliasForms:alias.length, groupCount:groups.length,
            ids:function(){ return ids.slice(); }};
  }

  return {build:build, fold:fold, dist:dist};
})();
