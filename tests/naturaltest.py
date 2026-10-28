from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio
from playwright.async_api import async_playwright
BUILDERS = open('giftest.py').read().split('BUILDERS = r"""')[1].split('"""')[0]
VSETUP = open('videotest.py').read().split('SETUP = r"""')[1].split('"""')[0]
async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROMIUM)
        page = await b.new_page(viewport={'width':1100,'height':950}); page.on('pageerror', lambda e: errs.append(str(e)))
        await page.goto(URL); await page.evaluate(BUILDERS); await page.evaluate(VSETUP)
        # GIF: 10 frames x 0.1s = 1.0s clip, sequence of two FULL shots = 4.0s
        await page.evaluate("""async () => { const W=160,H=90,P=T.pal(); window.TEST_PAL = P;
            const fr = Array.from({length:10}, (_, k) => ({x:0,y:0,w:W,h:H, idx:T.solid(W,H,k*20+3), delay:10, disposal:1, transparent:-1}));
            await loadFile(new File([T.gif(W,H,P,fr)], 'c.gif', {type:'image/gif'})); addFull(); }""")
        r = await page.evaluate("""() => { const tl = buildTimeline(), c = document.createElement('canvas'); c.width = 16; c.height = 9; const g = c.getContext('2d'); const o = [];
            for (const t of [0.05, 0.55, 0.95, 1.05, 2.35, 3.85]){ renderAtTime(g, 16, 9, t, tl); const d = g.getImageData(8, 4, 1, 1).data;
              let k = -1; for (let j = 0; j < 10; j++){ const [r,gg,bb] = TEST_PAL[j*20+3]; if (Math.abs(d[0]-r)+Math.abs(d[1]-gg)+Math.abs(d[2]-bb) < 6) k = j; } o.push(k); }
            return { media: { ...media }, total: tl.total, shown: o, tc: document.getElementById('tc').textContent, status: document.getElementById('status').textContent }; }""")
        exp = [0, 5, 9, 0, 3, 8]
        print('N1 GIF default:', r['media'], '| total', r['total'], '| frames', r['shown'], 'PASS' if r['shown'] == exp else f'FAIL expect {exp}')
        print('   transport:', r['tc'], '| status:', r['status'])
        await page.evaluate("() => selectMedia()")
        mi = await page.evaluate("() => ({ modes: [...document.querySelector('#inspector .seg').children].map(b => b.textContent), on: document.querySelector('#inspector .seg .on').textContent, val: document.querySelector('#inspector .field .val').textContent, fields: [...document.querySelectorAll('#inspector .field > label')].map(l => l.firstChild.textContent.trim()), note: document.querySelector('#inspector .note').textContent })")
        print('N2 media inspector:', mi)
        # switching: Fit clip → Natural resets to a clean 1×
        await page.evaluate("() => { const d = document.getElementById('speedMore'); if (d) d.open = true; }"); await page.locator('#inspector .seg button', has_text='Fit clip').click()
        a = await page.evaluate("() => [media.speed, document.getElementById('tc').textContent]")
        await page.evaluate("() => { const d = document.getElementById('speedMore'); if (d) d.open = true; }"); await page.locator('#inspector .seg button', has_text='Natural').click()
        n = await page.evaluate("() => [media.speed, document.getElementById('tc').textContent]")
        await page.evaluate("() => { const d = document.getElementById('speedMore'); if (d) d.open = true; }"); await page.locator('#inspector .seg button', has_text='Fit camera').click()
        f = await page.evaluate("() => [media.speed, document.getElementById('tc').textContent]")
        print('N3 Fit clip', a, '→ Natural', n, '→ Fit camera', f)
        # video: 2.0s clip, 4.0s sequence → loops
        await page.evaluate("async () => { await loadFile(new File([await makeClip()], 'clip.webm', {type:'video/webm'})); addFull(); }")
        r = await page.evaluate("async () => { const o = []; for (const t of [0.35, 1.75, 2.35, 3.85]) o.push(await shownAt(t)); return { media: { ...media }, shown: o }; }")
        print('N4 video default:', r['media'], '| frames at 0.35/1.75/2.35/3.85s:', r['shown'], 'PASS' if r['shown'] == [3, 17, 3, 18] else 'FAIL expect [3, 17, 3, 18]')
        # an old project saved with Auto still opens in Auto
        res = await page.evaluate("async () => { const p = await buildProject(false); p.media.speed = 'auto'; applyProject(p); return [media.speed, document.getElementById('tc').textContent]; }")
        print('N5 saved project keeps its mode:', res)
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
