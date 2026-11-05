# Build 234: messages and the library's progress are modals (showNotice, #importOverlay). Tests
# written before that load this so a finished import's outcome and any notice are put away at
# once, and they go on tapping the page as they always did. (The message text is still in the
# hidden #statusLineText, which some of them read.)
# Build 489: Artists, Albums and Songs now open sorted by Recent; tests written before that expect
# the A-Z order (letters, the A-Z rail), so they start with A-Z picked unless a test sets its own.
AUTO_NOTICE = """try{ if(!localStorage.getItem('radioPlayerLibSort')) localStorage.setItem('radioPlayerLibSort', JSON.stringify({ artists: 'az', albums: 'az', songs: 'az' })); }catch(e){}
document.addEventListener('DOMContentLoaded', function(){
  function watch(id, close){
    var o = document.getElementById(id);
    if(!o) return;
    new MutationObserver(function(){ if(o.classList.contains('open')) setTimeout(close, 0); }).observe(o, { attributes: true, attributeFilter: ['class'] });
  }
  watch('noticeOverlay', function(){ var o = document.getElementById('noticeOverlay'); if(o) o.classList.remove('open'); });
  watch('importOverlay', function(){ var o = document.getElementById('importOverlay'); if(o) o.classList.remove('open'); });
});"""
