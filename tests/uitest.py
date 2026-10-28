from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio, json
from playwright.async_api import async_playwright

EXE = CHROMIUM

LOAD_IMG = """
async () => {
  const c = document.createElement('canvas'); c.width = 1600; c.height = 900;
  const g = c.getContext('2d');
  const gr = g.createLinearGradient(0,0,1600,900); gr.addColorStop(0,'#1d3b6e'); gr.addColorStop(1,'#e8a33d');
  g.fillStyle = gr; g.fillRect(0,0,1600,900);
  g.fillStyle = '#fff'; for (let i=0;i<40;i++){ g.fillRect(i*40, 200 + (i%5)*90, 18, 18); }
  const blob = await new Promise(r => c.toBlob(r, 'image/png'));
  loadFile(new File([blob], 't.png', {type:'image/png'}));
  await new Promise(r => setTimeout(r, 400));
}
"""

async def drag(page, x0, y0, x1, y1):
    box = await page.locator('#vf').bounding_box()
    await page.mouse.move(box['x']+x0, box['y']+y0)
    await page.mouse.down()
    await page.mouse.move(box['x']+x1, box['y']+y1, steps=8)
    await page.mouse.up()

async def state(page):
    return await page.evaluate("""() => ({
      shots: shots.length, active: activeShot, link: selLink,
      kids: document.getElementById('tlRow').children.length,
      tc: document.getElementById('tc').textContent,
      insp: document.querySelector('#inspector:not([hidden]) .insp-head span') ? document.querySelector('#inspector .insp-head span').textContent : null,
      total: lastTotal,
      trackW: parseFloat(document.getElementById('tlTrack').style.width),
      scrollW: document.getElementById('tlScroll').scrollWidth,
      clientW: document.getElementById('tlScroll').clientWidth
    })""")

async def main():
    errors = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=EXE)
        page = await b.new_page(viewport={'width':1100,'height':900})
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: m.type == 'error' and errors.append(m.text))
        await page.goto(URL)
        await page.evaluate(LOAD_IMG)
        s = await state(page); print('1 loaded:', s)

        await drag(page, 300, 150, 520, 300)
        s = await state(page); print('2 drew shot 2:', {k:s[k] for k in ('shots','active','kids','tc','insp')})

        await drag(page, 650, 300, 820, 420)
        s = await state(page); print('3 drew shot 3:', {k:s[k] for k in ('shots','active','kids','tc','insp')})
        print('  fits width (no scroll):', s['scrollW'] <= s['clientW'] + 1, s['trackW'], s['clientW'])

        # link widths proportional? both default 3.0s → equal
        lw = await page.evaluate("() => [...document.querySelectorAll('.link')].map(l => parseFloat(l.style.width))")
        print('4 link widths (equal, stretched):', lw)

        # select first move and give it a crossfade, 6s, linear
        await page.locator('.link').nth(0).click()
        s = await state(page); print('5 link inspector:', s['insp'], 'selLink', s['link'])
        await page.locator('#inspector .trans-chips button', has_text='Fade').click()
        await page.locator('#inspector input[type=range]').evaluate("(r) => { r.value = 6; r.dispatchEvent(new Event('input')); r.dispatchEvent(new Event('change')); }")
        await page.locator('#inspector .style-chips button', has_text='Linear').click()
        info = await page.evaluate("() => ({ out: shots[0].out, cls: document.querySelector('.link').className, total: lastTotal, widths: [...document.querySelectorAll('.link')].map(l => parseFloat(l.style.width)) })")
        print('6 customized move:', info)

        # change default duration: customized move must keep 6s, other follows
        await page.evaluate("() => { const d = document.getElementById('dur'); d.value = 1; d.dispatchEvent(new Event('input')); }")
        tr = await page.evaluate("() => [effTrans(0), effTrans(1)].map(t => [t.kind, t.dur, t.ease, t.custom])")
        print('7 after default dur=1:', tr, 'total', await page.evaluate('lastTotal'))

        # select shot 2 via its card, set custom dwell, then reorder
        await page.locator('.card').nth(1).click()
        await page.locator('#inspector input[type=range]').evaluate("(r) => { r.value = 2; r.dispatchEvent(new Event('input')); r.dispatchEvent(new Event('change')); }")
        dot = await page.locator('.card').nth(1).locator('.cdot').count()
        print('8 shot 2 dwell custom dot:', dot == 1, 'dwell', await page.evaluate('shots[1].dwell'))

        # drag shot 2 on canvas: settings must survive geometry edits
        before = await page.evaluate('({x: shots[1].x, dwell: shots[1].dwell})')
        await drag(page, 410, 225, 470, 245)
        after = await page.evaluate('({x: shots[1].x, dwell: shots[1].dwell, out: shots[0].out})')
        print('9 moved shot keeps dwell:', before, '→', after)

        # preview: playhead moves along the strip
        await page.locator('#btnPreview').click()
        await page.wait_for_timeout(700)
        x1 = await page.evaluate("document.getElementById('tlScroll').scrollLeft")
        await page.wait_for_timeout(900)
        x2 = await page.evaluate("document.getElementById('tlScroll').scrollLeft")
        label = await page.locator('#btnPreview').text_content()
        print('10 preview playhead advancing:', x2 > x1, round(x1,1), '→', round(x2,1), '| button:', label)
        await page.locator('#btnPreview').click()   # stop
        print('   stopped:', await page.evaluate('previewRAF === 0'), await page.locator('#btnPreview').text_content())

        # scrub: drag along ruler
        rb = await page.locator('#tlScroll').bounding_box()
        await page.mouse.move(rb['x']+rb['width']/2, rb['y']+30)
        await page.mouse.wheel(260, 0); await page.wait_for_timeout(250)
        tc = await page.locator('#tc').text_content()
        print('11 scrub time readout:', tc)

        # time<->x round trip consistency
        rt = await page.evaluate("""() => { const tl = buildTimeline(); const out = [];
           for (const t of [0.2, 1.3, 4.0, 7.5]) out.push([t, +xToTime(timeToX(t, tl), tl).toFixed(3)]); return out; }""")
        print('12 time→x→time:', rt)

        await page.screenshot(path=OUT + '/desk.png', full_page=True)

        # GIF render end-to-end (small)
        await page.evaluate("() => { document.getElementById('outW').value = '480'; document.getElementById('fps').value = 10; }")
        await page.locator('#btnExport').click()
        await page.evaluate("() => $('btnGif').click()")
        await page.wait_for_function("() => document.querySelector('#media img')", timeout=60000)
        gif = await page.evaluate("() => ({ title: document.getElementById('monTitle').textContent, link: document.querySelector('#dl a').textContent, dlgOpen: document.getElementById('dlgExport').open })")
        print('13 GIF rendered:', gif)

        # Video render (WebCodecs path)
        await page.locator('#btnExport').click()
        await page.evaluate("() => $('btnVideo').click()")
        await page.wait_for_function("() => document.querySelector('#media video')", timeout=60000)
        vid = await page.evaluate("""async () => { const v = document.querySelector('#media video');
            await new Promise(r => { if (v.readyState >= 1) r(); else v.onloadedmetadata = r; setTimeout(r, 3000); });
            return { title: document.getElementById('monTitle').textContent, w: v.videoWidth, h: v.videoHeight }; }""")
        print('14 video rendered:', vid)

        # mobile: many shots → strip scrolls
        m = await b.new_page(viewport={'width':390,'height':844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        m.on('pageerror', lambda e: errors.append('mobile: ' + str(e)))
        await m.goto(URL)
        await m.evaluate(LOAD_IMG)
        s = await state(m); print('15 mobile 1 shot:', {k:s[k] for k in ('shots','scrollW','clientW')})
        await m.evaluate("() => { for (let k=0;k<2;k++){ shots.push(fitRect(400+k*300, 300, 400, 0)); } refreshTotal(); }")
        s = await state(m); tw = await m.evaluate("() => document.getElementById('tlTrack').offsetWidth"); print('16 mobile 3 shots fit in view:', tw <= s['clientW'] + 1, tw, s['clientW'])
        await m.evaluate("() => { for (let k=0;k<4;k++){ shots.push(fitRect(300+k*250, 500, 300, k*0.1)); } refreshTotal(); }")
        s = await state(m); print('17 mobile 7 shots scrolls:', s['scrollW'] > s['clientW'], s['scrollW'], s['clientW'])
        await m.locator('.link').nth(2).click()
        await m.screenshot(path=OUT + '/mobile.png', full_page=True)
        await m.keyboard.press('Escape')
        await m.evaluate("() => { if (src) deselect(); }"); await m.locator('#btnMenu').click()
        await m.wait_for_timeout(200)
        await m.screenshot(path=OUT + '/mobile_sheet.png')
        await b.close()
    print('ERRORS:', errors or 'none')

asyncio.run(main())
