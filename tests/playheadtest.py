from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio
from playwright.async_api import async_playwright
IMG = open('auditshots.py').read().split('IMG = r"""')[1].split('"""')[0]
VSETUP = open('videotest.py').read().split('SETUP = r"""')[1].split('"""')[0]
CENTER_T = "() => { const sc = $('tlScroll'); return +xToTime(sc.scrollLeft, curTL).toFixed(2); }"
async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROMIUM)
        ctx = await b.new_context(viewport={'width':390,'height':844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        m = await ctx.new_page(); m.on('pageerror', lambda e: errs.append(str(e)))
        cdp = await ctx.new_cdp_session(m)
        await m.goto(URL); await m.evaluate(IMG); await m.evaluate(VSETUP)
        await m.evaluate("() => { setTimeout(async () => { await loadFile(new File([await makeClip()], 'clip.webm', {type:'video/webm'})); media.speed = 'auto'; shots.push(fitRect(100, 60, 140, 0)); addFull(); deselect(); window.__a = 1; }, 0); }")
        await m.wait_for_function("() => window.__a"); await m.wait_for_timeout(400)
        g = await m.evaluate("() => { const sc = $('tlScroll'), h = $('centerHead').getBoundingClientRect(), r = sc.getBoundingClientRect(); return { line: !$('centerHead').hidden, lineAtCentre: Math.abs((h.left + h.width/2) - (r.left + r.width/2)) < 1.5, ruler: document.getElementById('ruler') ? 'still present' : 'removed', total: curTL.total, pad: getComputedStyle(sc).getPropertyValue('--pad').trim(), sw: sc.scrollWidth, cw: sc.clientWidth }; }")
        print('T1 fixed centre line:', g)
        # ends reach the line
        ends = await m.evaluate("async () => { const sc = $('tlScroll'); sc.scrollLeft = 0; await new Promise(r => setTimeout(r, 60)); const a = +xToTime(sc.scrollLeft, curTL).toFixed(2); sc.scrollLeft = 1e6; await new Promise(r => setTimeout(r, 60)); return [a, +xToTime(sc.scrollLeft, curTL).toFixed(2)]; }")
        print('T2 strip ends reach the line: start', ends[0], '| end', ends[1], '(total', g['total'], ')')
        # a finger swipe on the strip scrubs: the viewfinder shows the frame for the time under the line
        r = await m.evaluate("() => { const b = $('tlScroll').getBoundingClientRect(); return [b.left, b.top, b.width]; }")
        async def swipe(x0, x1, y):
            await cdp.send('Input.dispatchTouchEvent', {'type':'touchStart','touchPoints':[{'x':x0,'y':y}]})
            for k in range(1, 11): await cdp.send('Input.dispatchTouchEvent', {'type':'touchMove','touchPoints':[{'x':x0+(x1-x0)*k/10,'y':y}]})
            await cdp.send('Input.dispatchTouchEvent', {'type':'touchEnd','touchPoints':[]})
        await m.evaluate("() => { $('tlScroll').scrollLeft = 0; }"); await m.wait_for_timeout(200)
        await swipe(r[0] + r[2]*0.8, r[0] + r[2]*0.3, r[1] + 40); await m.wait_for_timeout(700)
        sc = await m.evaluate("async () => { const t = xToTime($('tlScroll').scrollLeft, curTL); await prepareFrame(t, curTL, 30); return { t: +t.toFixed(2), viewT: +viewT.toFixed(2), tc: $('tc').textContent, scrubShown, vf: which(vctx.getImageData(vf.width/2|0, vf.height/2|0, 1, 1).data), expect: which((() => { const c = document.createElement('canvas'); c.width = vf.width; c.height = vf.height; const g = c.getContext('2d'); renderAtTime(g, c.width, c.height, t, curTL); return g.getImageData(c.width/2|0, c.height/2|0, 1, 1).data; })()) }; }")
        print('T3 finger swipe scrubs:', sc, '| order unchanged:', await m.evaluate("() => shots.length"))
        # playback keeps the current moment under the line
        await m.locator('#btnPreview').click(); await m.wait_for_timeout(1200)
        pl = await m.evaluate(f"() => ({{ playing: !!previewRAF, centre: ({CENTER_T})(), viewT: +viewT.toFixed(2) }})")
        print('T4 during playback the line tracks the time:', pl, '| match:', abs(pl['centre'] - pl['viewT']) < 0.08)
        # touching the strip takes over
        await cdp.send('Input.dispatchTouchEvent', {'type':'touchStart','touchPoints':[{'x':r[0]+r[2]*0.5,'y':r[1]+40}]})
        await cdp.send('Input.dispatchTouchEvent', {'type':'touchEnd','touchPoints':[]})
        await m.wait_for_timeout(150)
        print('   touching the strip pauses playback:', await m.evaluate("() => previewRAF === 0"))
        await m.evaluate("() => deselect()")
        # tapping a card puts it under the line
        await m.wait_for_timeout(500)
        await m.locator('.card').nth(1).tap(); await m.wait_for_timeout(400)
        c = await m.evaluate(f"() => ({{ active: activeShot, centre: ({CENTER_T})(), span: [curTL.spans[2].t0, curTL.spans[2].t0 + curTL.spans[2].dur] }})")
        print('T5 tapped card 2 is under the line:', c['active'] == 1 and c['span'][0] <= c['centre'] <= c['span'][1], c)
        # Pin uses the moment under the line
        await swipe(r[0] + r[2]*0.6, r[0] + r[2]*0.45, r[1] + 40); await m.wait_for_timeout(600)
        t_line = await m.evaluate(CENTER_T)
        await m.locator('#toolPin').tap(); await m.wait_for_timeout(200)
        pin = await m.evaluate("() => [shots[1].pin, +(curTL.speed * 1).toFixed(3)]")
        print('T6 Pin at the line: line t =', t_line, '| pin clip time', pin[0], '| arrival now', await m.evaluate("() => +curTL.spans[2].t0.toFixed(2)"))
        await m.screenshot(path=OUT + '/ph_phone.png')
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
