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
        await m.evaluate("() => { setTimeout(async () => { await loadFile(await photo()); shots.push(fitRect(700, 450, 400, 0), fitRect(1150, 600, 360, 0.35)); deselect(); window.__a = 1; }, 0); }")
        await m.wait_for_function("() => window.__a"); await m.wait_for_timeout(300)
        async def touch(kind, pts): await cdp.send('Input.dispatchTouchEvent', {'type': kind, 'touchPoints': [{'x': x, 'y': y, 'id': i} for i, (x, y) in enumerate(pts)]})
        async def drag(a, b2, n=10):
            await touch('touchStart', [a])
            for k in range(1, n + 1): await touch('touchMove', [(a[0] + (b2[0]-a[0])*k/n, a[1] + (b2[1]-a[1])*k/n)])
            await touch('touchEnd', [])
        SCR = """(i) => { const r = vf.getBoundingClientRect(), k = r.width / vf.width; return cornersOf(shots[i]).map(([x, y]) => [+(r.left + x * scale * k).toFixed(1), +(r.top + y * scale * k).toFixed(1)]); }"""
        IMGC = "(i) => cornersOf(shots[i]).map(([x, y]) => [Math.round(x), Math.round(y)])"
        S = await m.evaluate("() => { const r = vf.getBoundingClientRect(); return { l: r.left, t: r.top, k: r.width / vf.width * scale }; }")
        # select shot 2 (tap its middle)
        await touch('touchStart', [(S['l'] + 700 * S['k'], S['t'] + 450 * S['k'])]); await touch('touchEnd', [])
        c0 = await m.evaluate(IMGC, 1); w0 = await m.evaluate("() => shots[1].w")
        br = (await m.evaluate(SCR, 1))[3]
        await drag((br[0] - 6, br[1] - 5), (br[0] + 34, br[1] + 25))          # grab just inside the corner
        c1 = await m.evaluate(IMGC, 1); w1 = await m.evaluate("() => shots[1].w")
        print('C1 corner drag grows it:', round(w0), '→', round(w1), '| opposite corner fixed:', c0[0], '→', c1[0], '| aspect kept:', await m.evaluate("() => +(shots[1].w / shots[1].h).toFixed(3)"), '| still selected:', await m.evaluate("() => activeShot"))
        # C2 a rotated shot: tap to select, drag its top-left corner outward
        await touch('touchStart', [(S['l'] + 1150 * S['k'], S['t'] + 600 * S['k'])]); await touch('touchEnd', [])
        d0 = await m.evaluate(IMGC, 2); wr0 = await m.evaluate("() => shots[2].w")
        tl = (await m.evaluate(SCR, 2))[0]
        await drag(tl, (tl[0] - 25, tl[1] - 10))
        d1 = await m.evaluate(IMGC, 2); wr1 = await m.evaluate("() => shots[2].w")
        print('C2 rotated shot: width', round(wr0), '→', round(wr1), '| opposite corner fixed:', d0[3], '→', d1[3], '| rotation kept:', await m.evaluate("() => +(shots[2].rot * 180 / Math.PI).toFixed(1)"))
        # C3 dragging the middle still moves it
        x0 = await m.evaluate("() => shots[2].x")
        mid = (S['l'] + (shots_x := 1150) * S['k'], S['t'] + 600 * S['k'])
        await drag(mid, (mid[0] - 40, mid[1]))
        print('C3 body drag moves, not resizes: x', round(x0), '→', round(await m.evaluate("() => shots[2].x")), '| width', round(wr1), '→', round(await m.evaluate("() => shots[2].w")))
        await m.screenshot(path=OUT + '/corner_touch.png')
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
