from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio
from playwright.async_api import async_playwright
SETUP = open('videotest.py').read().split('SETUP = r"""')[1].split('"""')[0]
async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROMIUM)
        page = await b.new_page(viewport={'width':1100,'height':950})
        page.on('pageerror', lambda e: errs.append(str(e)))
        await page.goto(URL); await page.evaluate(SETUP)
        await page.evaluate("""async () => { await loadFile(new File([await makeClip()], 'clip.webm', {type:'video/webm'}));
            shots.push(fitRect(100, 60, 140, 0)); addFull();
            setOut(0, 'dur', 3); setOut(1, 'dur', 1);           // 3:1 moves, default 0.5s dwells → 5.5s unscaled
            media.speed = 'fit'; refreshTotal(); }""")
        r = await page.evaluate("""() => { const tl = buildTimeline();
            return { total: tl.total, speed: tl.speed, k: +tl.k.toFixed(4),
                     spans: tl.spans.map(s => +s.dur.toFixed(3)),
                     ratio: +(tl.spans[1].dur / tl.spans[3].dur).toFixed(3),
                     links: [...document.querySelectorAll('.link .d')].map(e => e.textContent),
                     tc: document.getElementById('tc').textContent }; }""")
        print('F1 Real time timeline:', r)
        print('   total == clip (2.0s):', abs(r['total'] - 2.0) < 1e-9, '| speed 1x:', r['speed'] == 1, '| 3:1 kept:', r['ratio'] == 3.0, '| k = 2/5.5:', abs(r['k'] - 2/5.5) < 1e-4)

        res = await page.evaluate("""async () => { const o = []; for (let n = 0; n < 20; n++){ const t = (n + 0.5) / 10; o.push(await shownAt(t)); } return o; }""")
        print('F2 output t=(n+.5)/10 shows source frame n:', res, 'PASS' if res == list(range(20)) else 'FAIL')

        # trimmed: Real time follows the trim (1.0s clip → 1.0s sequence starting at frame 5)
        await page.evaluate("() => { media.trimIn = 0.5; media.trimOut = 1.5; refreshTotal(); }")
        res = await page.evaluate("""async () => { const o = []; for (let n = 0; n < 10; n++) o.push(await shownAt((n + 0.5) / 10)); return [buildTimeline().total, o]; }""")
        print('F3 trimmed 0.5–1.5s:', res, 'PASS' if abs(res[0]-1.0) < 1e-9 and res[1] == list(range(5,15)) else 'FAIL')

        # inspectors show setting → actual; loop/hold hidden unless Manual
        await page.evaluate("() => { media.trimIn = 0; media.trimOut = src.duration; refreshTotal(); selectLink(0); }")
        linkVal = await page.evaluate("() => [...document.querySelectorAll('#inspector .val')].map(e => e.textContent)")
        await page.evaluate("() => selectMedia()")
        mi = await page.evaluate("() => ({ fields: [...document.querySelectorAll('#inspector .field > label')].map(l => l.firstChild.textContent.trim()), btns: [...document.querySelectorAll('#inspector .seg')][0].innerText.split('\\n'), on: document.querySelector('#inspector .seg .on').textContent, note: document.querySelector('#inspector .note').textContent })")
        print('F4 move inspector value:', linkVal)
        print('F5 media inspector:', mi)
        await page.evaluate("() => { const d = document.getElementById('speedMore'); if (d) d.open = true; }"); await page.locator('#inspector .seg button', has_text='Natural').click()
        mi2 = await page.evaluate("() => ({ speed: media.speed, fields: [...document.querySelectorAll('#inspector .field > label')].map(l => l.firstChild.textContent.trim()) })")
        print('F6 Natural shows loop/hold:', mi2)

        # GIF source too: clock GIF 10 frames over 1.0s
        await page.evaluate(open('giftest.py').read().split('BUILDERS = r"""')[1].split('"""')[0])
        await page.evaluate("""async () => { const W=160,H=90,P=T.pal(); window.TEST_PAL = P;
            const fr = Array.from({length:10}, (_, k) => ({x:0,y:0,w:W,h:H, idx:T.solid(W,H,k*20+3), delay:10, disposal:1, transparent:-1}));
            await loadFile(new File([T.gif(W,H,P,fr)], 'c.gif', {type:'image/gif'})); addFull(); media.speed = 'fit'; refreshTotal(); }""")
        r = await page.evaluate("""() => { const tl = buildTimeline(), c = document.createElement('canvas'); c.width = 16; c.height = 9; const g = c.getContext('2d'); const o = [];
            for (let n = 0; n < 10; n++){ renderAtTime(g, 16, 9, (n + .5) / 10, tl); const d = g.getImageData(8, 4, 1, 1).data;
              let k = -1; for (let j = 0; j < 10; j++){ const [r,gg,bb] = TEST_PAL[j*20+3]; if (Math.abs(d[0]-r)+Math.abs(d[1]-gg)+Math.abs(d[2]-bb) < 6) k = j; } o.push(k); }
            return [tl.total, o]; }""")
        print('F7 GIF Real time:', r, 'PASS' if abs(r[0]-1.0) < 1e-9 and r[1] == list(range(10)) else 'FAIL')
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
