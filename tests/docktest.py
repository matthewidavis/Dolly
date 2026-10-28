from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio
from playwright.async_api import async_playwright
VSETUP = open('videotest.py').read().split('SETUP = r"""')[1].split('"""')[0]
GEO = """() => { const i = document.getElementById('inspector').getBoundingClientRect(), t = document.getElementById('timeline').getBoundingClientRect(), tr = document.getElementById('transport').getBoundingClientRect();
  return { h: Math.round(i.height), top: Math.round(i.top), timelineTop: Math.round(t.top), transportBottom: Math.round(tr.bottom) }; }"""
async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROMIUM)
        m = await b.new_page(viewport={'width':390,'height':844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        m.on('pageerror', lambda e: errs.append(str(e)))
        await m.goto(URL); await m.evaluate(VSETUP)
        await m.evaluate("() => { setTimeout(async () => { await loadFile(new File([await makeClip()], 'clip.webm', {type:'video/webm'})); shots.push(fitRect(100, 60, 140, 0)); addFull(); deselect(); document.getElementById('status').classList.remove('show'); window.__a = 1; }, 0); }")
        await m.wait_for_function("() => window.__a"); await m.wait_for_timeout(300)
        rows = []
        async def meas(label): await m.wait_for_timeout(300); rows.append((label, await m.evaluate(GEO)))
        await m.locator('#trayTiming').tap(); await meas('Timing, all closed')
        await m.screenshot(path=OUT + '/dock1.png')
        await m.locator('details.acc[data-key=moves] summary').tap(); await m.wait_for_timeout(500)
        await meas('Timing, Moves open')
        sec = await m.evaluate("() => { const box = document.getElementById('inspector'), head = box.querySelector('.insp-head').getBoundingClientRect(), s = document.querySelector('details.acc[data-key=moves] summary').getBoundingClientRect(); return Math.round(s.top - head.bottom); }")
        await m.screenshot(path=OUT + '/dock2.png')
        await m.locator('details.acc[data-key=camera] summary').tap(); await m.wait_for_timeout(500)
        sec2 = await m.evaluate("() => { const box = document.getElementById('inspector'), head = box.querySelector('.insp-head').getBoundingClientRect(), s = document.querySelector('details.acc[data-key=camera] summary').getBoundingClientRect(); return Math.round(s.top - head.bottom); }")
        await meas('Timing, Camera open')
        await m.locator('#inspector .done-btn').tap(); await m.locator('#trayLook').tap(); await meas('Look')
        await m.locator('#inspector .done-btn').tap(); await m.locator('#traySpeed').tap(); await meas('Speed')
        await m.locator('#inspector .done-btn').tap(); await m.locator('#traySound').tap(); await meas('Sound')
        await m.locator('#inspector .done-btn').tap(); await m.locator('.card').nth(1).tap(); await m.wait_for_timeout(200); await m.locator('#toolHold').tap(); await meas('Hold tool panel')
        for label, g in rows: print(f'  {label:20s}', g)
        hs = {g['h'] for _, g in rows}
        print('D1 every panel the same height:', len(hs) == 1, hs)
        print('D2 panel top = timeline top:', all(abs(g['top'] - g['timelineTop']) <= 1 for _, g in rows), '| play controls clear above:', all(g['transportBottom'] <= g['top'] for _, g in rows))
        print('D3 an opened section lands just under the header (px gap):', sec, sec2)
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
