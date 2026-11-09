"""Build 504: reordering by touch is press-and-hold, then drag (no grips). This drives it with real touch events."""
async def hold_drag(pg, cdp, x0, y0, x1, y1, hold=650, steps=14, dwell=150):
    pt = lambda x, y: [{'x': x, 'y': y, 'id': 1}]
    await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': pt(x0, y0)})
    await pg.wait_for_timeout(hold)
    for i in range(1, steps + 1):
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': pt(x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps)})
        await pg.wait_for_timeout(30)
    await pg.wait_for_timeout(dwell)
    await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    await pg.wait_for_timeout(400)
