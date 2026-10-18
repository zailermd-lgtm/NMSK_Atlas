var nerveGroupsCtl = NMSKNerveGroups({
  url:"plexus_groups.json", toolbar:document.getElementById("topright"), toolClass:"pill",
  mark:function(ids, replace){ return selCtl ? selCtl.markIds(ids, true, replace, true) : 0; },
  clear:function(){ if (selCtl) selCtl.clear(); },
  highlight:function(){ if (selCtl) selCtl.preset("hlsel"); },
  isPhone:function(){ return window.innerWidth <= 900; },
  onLoaded:function(){}
});
nerveGroupsCtl.load();
window.__nerveGroupsState = function(){ return nerveGroupsCtl.state(); };
