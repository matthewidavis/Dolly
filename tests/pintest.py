from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio
from playwright.async_api import async_playwright
VSETUP = open('videotest.py').read().split('SETUP = r"""')[1].split('"""')[0]
ARRIVE = """(i) => { const tl = buildTimeline(); return +tl.spans[2 * i].t0.toFixed(4); }"""
PINS = """() => buildTimeline().pins.map(p => [p.i, p.ok, p.why])"""
FRAME_AT_ARRIVAL = """async (i) => { const tl = buildTimeline(), t = tl.spans[2 * i].t0 + 0.001; await prepareFrame(t, tl, 10);
  const c = document.createElement('canvas'); c.width = 64; c.height = 36; const g = c.getContext('2d');
  renderAtTime(g, 64, 36, t, tl, 10); return which(g.getImageData(32, 18, 1, 1).data); }"""
async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROMIUM)
        page = await b.new_page(viewport={'width':1100,'height':950}); page.on('pageerror', lambda e: errs.append(str(e)))
        await page.goto(URL); await page.evaluate(VSETUP)
        # 2.0 s clip (20 colour frames). Shots: FULL, two full-frame copies, FULL → crops show the whole frame.
        await page.evaluate("async () => { await loadFile(new File([await makeClip()], 'clip.webm', {type:'video/webm'})); addFull(); addFull(); addFull(); $('fps').value = 10; refreshTotal(); }")
        base = await page.evaluate(ARRIVE, 2)
        print('P0 unpinned: shot 3 arrives at', base, 's (0.5+3+0.5+3)')

        # pin shot 3 to clip time 2.6 (loop 2, 0.6 s in) via the real UI: select it, set the playhead, press Pin
        await page.evaluate("() => { selectShot(2); viewT = 2.6; refreshTotal(); }")
        label = await page.evaluate("() => document.getElementById('pinBtn').textContent")
        await page.locator('#pinBtn').click()
        r = await page.evaluate(f"async () => ({{ arrive: ({ARRIVE})(2), pins: ({PINS})(), status: document.getElementById('status').textContent, total: +buildTimeline().total.toFixed(3) }})")
        k = await page.evaluate(FRAME_AT_ARRIVAL, 2)
        print('P1 Pin button read:', repr(label), '→', r, '| frame shown on arrival:', k, '(expect 6: clip 0.6 s)', 'PASS' if abs(r['arrive'] - 2.6) < 1e-6 and k == 6 else 'FAIL')
        badge = await page.evaluate("() => { const e = document.querySelectorAll('.card')[2].querySelector('.pinb'); return e && [e.textContent, e.className]; }")
        note = await page.evaluate("() => document.querySelector('#inspector .note').textContent")
        print('   card badge:', badge, '| inspector:', note)

        # at 2× the same clip moment arrives at half the output time
        await page.evaluate("() => { media.speed = 2; media.motion = 'off'; refreshTotal(); }")
        print('P2 at 2× arrival =', await page.evaluate(ARRIVE, 2), '(expect 1.3) | frame:', await page.evaluate(FRAME_AT_ARRIVAL, 2), '(expect 6)')
        await page.evaluate("() => { media.speed = 1; media.motion = 'auto'; refreshTotal(); }")

        # red pins: first shot, out of order, too tight
        await page.evaluate("() => { shots[0].pin = 1; refreshTotal(); }")
        print('P3 pin on first shot:', await page.evaluate(PINS)); await page.evaluate("() => { delete shots[0].pin; refreshTotal(); }")
        await page.evaluate("() => { shots[1].pin = 3.0; refreshTotal(); }")
        print('P4 shot 2 at 3.0 after shot 3 at 2.6:', await page.evaluate(PINS))
        await page.evaluate("() => { shots[1].pin = 2.55; refreshTotal(); }")
        print('P5 shot 2 at 2.55, 0.05 s before shot 3:', await page.evaluate(PINS))
        await page.evaluate("() => { shots[1].pin = 1.2; refreshTotal(); }")
        r = await page.evaluate(f"() => [({PINS})(), ({ARRIVE})(1), ({ARRIVE})(2)]")
        print('P6 two valid pins (1.2, 2.6):', r)
        # a red pin explains itself and its badge turns red
        await page.evaluate("() => { shots[1].pin = 3.0; refreshTotal(); selectShot(2); }")
        print('   red pin UI (shot 3, the later one):', await page.evaluate("() => [document.querySelector('#inspector .note.bad') && document.querySelector('#inspector .note.bad').textContent, document.querySelectorAll('.card')[2].querySelector('.pinb').className]"))
        await page.evaluate("() => { shots[1].pin = 1.2; refreshTotal(); }")

        # reorder carries pins; out of order turns red
        await page.evaluate("() => { const [s0] = shots.splice(2, 1); shots.splice(1, 0, s0); refreshTotal(); }")
        print('P7 after moving the 2.6 shot before the 1.2 shot:', await page.evaluate(PINS))
        await page.evaluate("() => undo()"); await page.wait_for_timeout(30)
        print('   undo:', await page.evaluate(PINS))

        # Fit clip: pinning switches to Fit camera; Fit camera still ends with the clip
        await page.evaluate("() => { delete shots[1].pin; delete shots[2].pin; media.speed = 'auto'; refreshTotal(); selectShot(2); viewT = 1.0; refreshTotal(); }")
        spd = await page.evaluate("() => curTL.speed")
        await page.locator('#pinBtn').click()
        r = await page.evaluate(f"() => ({{ mode: media.speed, total: +buildTimeline().total.toFixed(4), arrive: ({ARRIVE})(2), pin: shots[2].pin, status: document.getElementById('status').textContent }})")
        print('P8 pin in Fit clip (speed was', round(spd, 3), '):', r)
        await page.evaluate("() => { shots[2].pin = 2.5; refreshTotal(); }")
        print('P9 Fit camera pin after the clip ends:', await page.evaluate(PINS), '| total still', await page.evaluate("() => +buildTimeline().total.toFixed(3)"))

        # unpin with the same button; projects keep pins
        await page.evaluate("() => { shots[2].pin = 1.0; media.speed = 1; refreshTotal(); selectShot(2); }")
        await page.locator('#pinBtn').click()
        print('P10 tap again unpins:', await page.evaluate("() => shots[2].pin === undefined"), '|', await page.evaluate("() => document.getElementById('status').textContent"))
        r = await page.evaluate("async () => { shots[2].pin = 1.7; refreshTotal(); const p = await buildProject(false); shots.forEach(s => delete s.pin); applyProject(p); return shots.map(s => s.pin ?? null); }")
        print('P11 project round trip of pins:', r)

        # still images: no pin controls
        await page.evaluate("async () => { const c = document.createElement('canvas'); c.width = 400; c.height = 225; const f = new File([await new Promise(r => c.toBlob(r))], 'x.png', {type:'image/png'}); await loadFile(f); shots.push(fitRect(200, 100, 120, 0)); refreshTotal(); selectShot(1); }")
        print('P12 still image has no Pin button:', await page.evaluate("() => !document.getElementById('pinBtn')"))
        await b.close()

        # phone look: badge + marker + inspector
        b = await p.chromium.launch(executable_path=CHROMIUM)
        m = await b.new_page(viewport={'width':390,'height':844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        m.on('pageerror', lambda e: errs.append('m: ' + str(e)))
        await m.goto(URL); await m.evaluate(VSETUP)
        await m.evaluate("async () => { await loadFile(new File([await makeClip()], 'clip.webm', {type:'video/webm'})); shots.push(fitRect(100, 60, 140, 0)); addFull(); shots[1].pin = 1.2; shots[2].pin = 0.9; refreshTotal(); selectShot(2); }")
        await m.wait_for_timeout(400)
        box = await m.locator('#timeline').bounding_box()
        await m.screenshot(path=OUT + '/pins_mobile.png', clip={'x': 0, 'y': box['y'] - 4, 'width': 390, 'height': 600})
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
