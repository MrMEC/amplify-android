"""Build 542: press, hold and drag one tile onto another with synthetic touch events (for tests that
drive touch by dispatching TouchEvents rather than CDP). before=True drops it in front of the target."""
JS = """([rowSel, name, target, before]) => {
  var tiles = Array.from(document.querySelectorAll(rowSel));
  var nm = function(t){ var e = t.querySelector('.tile-name'); return e ? e.textContent : ''; };
  var a = tiles.filter(function(t){ return nm(t) === name; })[0], b = tiles.filter(function(t){ return nm(t) === target; })[0];
  a.scrollIntoView({block:'center', inline:'center'});
  var ra = a.getBoundingClientRect();
  var tc = new Touch({identifier: 7, target: a, clientX: ra.left + 20, clientY: ra.top + 20});
  a.dispatchEvent(new TouchEvent('touchstart', {touches:[tc], targetTouches:[tc], changedTouches:[tc], bubbles:true, cancelable:true}));
  window.__sd = { a: a, b: b, before: before };
}"""
MOVE = """() => {
  var d = window.__sd, rb = d.b.getBoundingClientRect(), ra = d.a.getBoundingClientRect();
  var x1 = d.before ? rb.left + rb.width * 0.2 : rb.left + rb.width * 0.8, y1 = rb.top + rb.height / 2;
  var x0 = ra.left + 20, y0 = ra.top + 20;
  for(var i = 1; i <= 12; i++){
    var x = x0 + (x1 - x0) * i / 12, y = y0 + (y1 - y0) * i / 12;
    var tc = new Touch({identifier: 7, target: d.a, clientX: x, clientY: y});
    d.a.dispatchEvent(new TouchEvent('touchmove', {touches:[tc], targetTouches:[tc], changedTouches:[tc], bubbles:true, cancelable:true}));
  }
  var te = new Touch({identifier: 7, target: d.a, clientX: x1, clientY: y1});
  d.a.dispatchEvent(new TouchEvent('touchend', {touches:[], changedTouches:[te], bubbles:true, cancelable:true}));
}"""
async def syn_drag(pg, row_sel, name, target, before=True):
    await pg.evaluate(JS, [row_sel, name, target, before])
    await pg.wait_for_timeout(560)
    await pg.evaluate(MOVE)
    await pg.wait_for_timeout(500)
