var nerveGroupsCtl = NMSKNerveGroups({
  url:"plexus_groups.json", toolbar:document.getElementById("tools"), toolClass:"tool",
  mount:function(){ return document.querySelector('#systems .sys-row[data-cat="nerve"]'); },   // Q262: inside the Nerves system row, not the top toolbar
  mark:function(ids, replace){ return selCtl ? selCtl.markIds(ids, true, replace, true) : 0; },
  clear:function(){ if (selCtl) selCtl.clear(); },
  highlight:function(){ if (selCtl) selCtl.preset("hlsel"); },
  isPhone:function(){ return !!app && app.classList.contains("phone"); },
  onLoaded:function(){}
});
nerveGroupsCtl.load();
window.__nerveGroupsState = function(){ return nerveGroupsCtl.state(); };
