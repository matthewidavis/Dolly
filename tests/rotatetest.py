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
        await m.evaluate("() => { setTimeout(async () => { await loadFile(await photo()); shots.push(fitRect(800, 500, 380, 0), fitRect(1450, 140, 220, 0)); deselect(); window.__a = 1; }, 0); }")
        await m.wait_for_function("() => window.__a"); await m.wait_for_timeout(300)
        geo = await m.evaluate("() => { const r = vf.getBoundingClientRect(), s = document.querySelector('.stage-inner').getBoundingClientRect(); return { l: r.left, t: r.top, w: r.width, h: r.height, k: r.width / vf.width * scale, sl: s.left, st: s.top, sw: s.width, sh: s.height }; }")
        S = lambda ix, iy: (geo['l'] + ix * geo['k'], geo['t'] + iy * geo['k'])
        async def touch(kind, pts): await cdp.send('Input.dispatchTouchEvent', {'type': kind, 'touchPoints': [{'x': x, 'y': y, 'id': i} for i, (x, y) in enumerate(pts)]})
        rot = lambda i: m.evaluate(f"() => +((shots[{i}].rot || 0) * 180 / Math.PI).toFixed(2)")
        # select shot 2 with a tap
        await touch('touchStart', [S(800, 500)]); await touch('touchEnd', [])
        knob = await m.evaluate("() => { const rh = rotHandle(sel), r = vf.getBoundingClientRect(), k = r.width / vf.width; return [r.left + rh.x * k, r.top + rh.y * k]; }")
        c = S(800, 500)
        # K1 one finger on the knob: swing it 30° around the centre
        a0 = math.atan2(knob[1] - c[1], knob[0] - c[0]); rr = math.hypot(knob[0] - c[0], knob[1] - c[1])
        await touch('touchStart', [knob])
        for k in range(1, 11):
            a = a0 + math.radians(30) * k / 10
            await touch('touchMove', [(c[0] + rr * math.cos(a), c[1] + rr * math.sin(a))])
        await touch('touchEnd', [])
        r1 = await rot(1)
        # K2 swing back to 2° short of level → snaps to exactly 0
        knob = await m.evaluate("() => { const rh = rotHandle(sel), r = vf.getBoundingClientRect(), k = r.width / vf.width; return [r.left + rh.x * k, r.top + rh.y * k]; }")
        a0 = math.atan2(knob[1] - c[1], knob[0] - c[0])
        await touch('touchStart', [knob])
        for k in range(1, 11):
            a = a0 - math.radians(28) * k / 10
            await touch('touchMove', [(c[0] + rr * math.cos(a), c[1] + rr * math.sin(a))])
        await touch('touchEnd', [])
        r2 = await rot(1)
        print('K1 knob turns the shot:', r1, '° (expect ~30) | K2 back near level snaps:', r2, '° | still selected:', await m.evaluate("() => activeShot"))
        # K3 twist with the second finger on the grey surround, outside the picture
        f1 = S(800, 500); f2 = (geo['sl'] + geo['sw'] - 6, geo['st'] + geo['sh'] - 10)
        outside = not (geo['l'] <= f2[0] <= geo['l'] + geo['w'] and geo['t'] <= f2[1] <= geo['t'] + geo['h'])
        mid = ((f1[0] + f2[0]) / 2, (f1[1] + f2[1]) / 2); rad = math.hypot(f2[0] - f1[0], f2[1] - f1[1]) / 2; base = math.atan2(f2[1] - f1[1], f2[0] - f1[0])
        def pts(a): return [(mid[0] - rad * math.cos(a), mid[1] - rad * math.sin(a)), (mid[0] + rad * math.cos(a), mid[1] + rad * math.sin(a))]
        await touch('touchStart', [f1]); await touch('touchStart', pts(base))
        for k in range(1, 11): await touch('touchMove', pts(base + math.radians(-15) * k / 10))
        await touch('touchEnd', [])
        print('K3 twist with a finger on the surround (outside the picture:', outside, '):', await rot(1), '° (expect ~-15)')
        # K4 a small shot near the edge: pinch with fingers wider than the shot
        await touch('touchStart', [S(120, 900)]); await touch('touchEnd', [])           # deselect
        await touch('touchStart', [S(1450, 140)]); await touch('touchEnd', [])          # select shot 3
        w0 = await m.evaluate("() => shots[2].w")
        cc = S(1450, 140)
        await touch('touchStart', [(cc[0] - 40, cc[1] + 30), (cc[0] + 40, cc[1] + 30)])
        for k in range(1, 9): await touch('touchMove', [(cc[0] - 40 - 25 * k / 8, cc[1] + 30), (cc[0] + 40 + 25 * k / 8, cc[1] + 30)])
        await touch('touchEnd', [])
        print('K4 pinch on a small edge shot: width', round(w0), '→', round(await m.evaluate("() => shots[2].w")))
        await m.screenshot(path=OUT + '/rot_touch.png')
        await b.close()
        # K5 desktop mouse knob unchanged
        b = await p.chromium.launch(executable_path=CHROMIUM)
        d = await b.new_page(viewport={'width':1100,'height':900}); d.on('pageerror', lambda e: errs.append(str(e)))
        await d.goto(URL); await d.evaluate(IMG)
        await d.evaluate("() => { setTimeout(async () => { await loadFile(await photo()); shots.push(fitRect(800, 500, 380, 0)); refreshTotal(); selectShot(1); window.__a = 1; }, 0); }")
        await d.wait_for_function("() => window.__a"); await d.wait_for_timeout(200)
        g = await d.evaluate("() => { const rh = rotHandle(sel), r = vf.getBoundingClientRect(), k = r.width / vf.width, c = ctr(sel); return { kx: r.left + rh.x * k, ky: r.top + rh.y * k, cx: r.left + c.cx * scale * k, cy: r.top + c.cy * scale * k }; }")
        rr = math.hypot(g['kx'] - g['cx'], g['ky'] - g['cy']); a0 = math.atan2(g['ky'] - g['cy'], g['kx'] - g['cx'])
        await d.mouse.move(g['kx'], g['ky']); await d.mouse.down()
        for k in range(1, 11):
            a = a0 + math.radians(20) * k / 10; await d.mouse.move(g['cx'] + rr * math.cos(a), g['cy'] + rr * math.sin(a))
        await d.mouse.up()
        print('K5 desktop mouse knob:', await d.evaluate("() => +((shots[1].rot || 0) * 180 / Math.PI).toFixed(2)"), '° (expect ~20)')
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
