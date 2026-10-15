# Build 228: deletes ask first (confirmDelete). Tests written before that load this so the dialog
# is confirmed automatically and they go on checking what they always did.
AUTO_CONFIRM = """document.addEventListener('DOMContentLoaded', function(){
  var o = document.getElementById('confirmOverlay');
  if(!o) return;
  new MutationObserver(function(){ if(o.classList.contains('open')) document.getElementById('confirmOk').click(); }).observe(o, { attributes: true, attributeFilter: ['class'] });
});"""
