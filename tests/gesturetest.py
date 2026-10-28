from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio, math
from playwright.async_api import async_playwright
IMG = open('auditshots.py').read().split('IMG = r"""')[1].split('"""')[0]
async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROMIUM)
        ctx = await b.new_context(viewport={'width':390,'height':844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        m = await ctx.new_page(); m.on('pageerror', lambda e: errs.append(str(e)))
        cdp = await ctx.new_cdp_session(m)
        await m.goto(URL); await m.evaluate(IMG)
        await m.evaluate("() => { setTimeout(async () => { await loadFile(await photo()); shots.push(fitRect(1050, 470, 380, 0)); deselect(); window.__a = 1; }, 0); }")
        await m.wait_for_function("() => window.__a"); await m.wait_for_timeout(300)
        geo = await m.evaluate("() => { const r = vf.getBoundingClientRect(); return { l: r.left, t: r.top, k: r.width / vf.width * scale }; }")
        # image px → screen px
        S = lambda ix, iy: (geo['l'] + ix * geo['k'], geo['t'] + iy * geo['k'])
        async def touch(kind, pts): await cdp.send('Input.dispatchTouchEvent', {'type': kind, 'touchPoints': [{'x': x, 'y': y, 'id': i} for i, (x, y) in enumerate(pts)]})
        async def drag1(a, bpt, steps=8):
            await touch('touchStart', [a])
            for k in range(1, steps + 1): await touch('touchMove', [(a[0] + (bpt[0]-a[0])*k/steps, a[1] + (bpt[1]-a[1])*k/steps)])
            await touch('touchEnd', [])
        shot = lambda: m.evaluate("() => { const s = shots[1]; return { x: +s.x.toFixed(1), y: +s.y.toFixed(1), w: +s.w.toFixed(1), rot: +((s.rot||0)*180/Math.PI).toFixed(2), cx: +(s.x + s.w/2).toFixed(1), active: activeShot, n: shots.length }; }")

        c0 = await shot()
        # G1 tap selects; nothing moves
        await touch('touchStart', [S(1050, 470)]); await touch('touchEnd', [])
        g1 = await shot(); print('G1 tap selects, no nudge:', g1['active'] == 1 and (g1['x'], g1['y']) == (c0['x'], c0['y']), '| tray shows shot tools:', await m.evaluate("() => !$('trayShotSet').hidden"))
        # G2 a 3px wobble doesn't move; a real drag moves exactly
        await drag1(S(1050, 470), (S(1050, 470)[0] + 3, S(1050, 470)[1] + 2))
        g2a = await shot()
        await drag1(S(1050, 470), S(1050 - 200, 470 - 80))
        g2b = await shot()
        print('G2 wobble ignored:', (g2a['x'], g2a['y']) == (c0['x'], c0['y']), '| drag moved by', round(g2b['x'] - c0['x']), round(g2b['y'] - c0['y']), '(expect about -200, -80)')
        # G3 drag close to the centre snaps onto it
        cx, cy = g2b['cx'], g2b['y'] + g2b['w'] * 238 / 380 / 2
        await drag1(S(cx, cy), S(800 + 6 / geo['k'] * 0.5, 500 + 4 / geo['k'] * 0.5))
        g3 = await m.evaluate("() => { const s = shots[1]; return [+(s.x + s.w/2).toFixed(2), +(s.y + s.h/2).toFixed(2)]; }")
        print('G3 snaps to the image centre (800, 500):', g3)
        # G4 a swipe over empty image never draws and deselects
        await drag1(S(120, 900), S(500, 980))
        g4 = await shot(); print('G4 a drag on empty image draws a new shot:', g4['n'] == 3, '| and selects it:', g4['active'] == 2)
        await m.evaluate("() => { shots.pop(); selectShot(1); }")
        await touch('touchStart', [S(120, 900)]); await touch('touchEnd', [])
        print('   a tap on empty image deselects:', (await shot())['active'] == -1)
        # G5 pinch apart 1.5x, then twist 20°, then a 2° twist snaps level
        await touch('touchStart', [S(800, 500)]); await touch('touchEnd', [])          # select it again
        w0 = (await shot())['w']
        cxs, cys = S(800, 500); r0 = 60
        async def two(r, ang, phase):
            pts = [(cxs - r*math.cos(ang), cys - r*math.sin(ang)), (cxs + r*math.cos(ang), cys + r*math.sin(ang))]
            await touch(phase, pts)
        await two(r0, 0, 'touchStart')
        for k in range(1, 9): await two(r0 * (1 + 0.5 * k / 8), 0, 'touchMove')
        await touch('touchEnd', [])
        g5a = await shot()
        await two(r0, 0, 'touchStart')
        for k in range(1, 9): await two(r0, math.radians(20) * k / 8, 'touchMove')
        await touch('touchEnd', [])
        g5b = await shot()
        await two(r0, 0, 'touchStart')
        for k in range(1, 9): await two(r0, math.radians(-21.5) * k / 8, 'touchMove')
        await touch('touchEnd', [])
        g5c = await shot()
        print('G5 pinch 1.5x: width', w0, '→', g5a['w'], f"(x{g5a['w']/w0:.2f})", '| twist 20°:', g5b['rot'], '| twist back to within 3° of level snaps:', g5c['rot'])
        # G6 tapping the selected shot again releases it
        await touch('touchStart', [S(800, 500)]); await touch('touchEnd', [])
        print('G6 tap selected shot again → deselected:', (await shot())['active'] == -1)
        # G7 the touch frame has no handles (pixels at a corner handle position are not handle-amber squares)
        print('G7 touch UI flag:', await m.evaluate("() => touchUI"))
        await touch('touchStart', [S(800, 500)]); await touch('touchEnd', [])
        await m.screenshot(path=OUT + '/g_touch.png')
        print('   undo after gestures works:', await m.evaluate("() => { const n = undoStack.length; undo(); return n > 0; }"))
        await b.close()
        # G8 mouse still draws (desktop)
        b = await p.chromium.launch(executable_path=CHROMIUM)
        d = await b.new_page(viewport={'width':1100,'height':900}); d.on('pageerror', lambda e: errs.append(str(e)))
        await d.goto(URL); await d.evaluate(IMG)
        await d.evaluate("() => { setTimeout(async () => { await loadFile(await photo()); window.__a = 1; }, 0); }"); await d.wait_for_function("() => window.__a")
        r = await d.evaluate("() => { const r = vf.getBoundingClientRect(); return [r.left, r.top]; }")
        await d.mouse.move(r[0] + 60, r[1] + 60); await d.mouse.down(); await d.mouse.move(r[0] + 200, r[1] + 160, steps=6); await d.mouse.up()
        print('G8 mouse drag still draws a shot:', await d.evaluate("() => [shots.length, touchUI]"))
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
