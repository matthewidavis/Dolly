from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio, hashlib
from playwright.async_api import async_playwright
EXE = CHROMIUM
IMG = open('projtest.py').read().split('IMG = r"""')[1].split('"""')[0]
CONTRAST = r"""() => {
  const v = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const rgb = h => { h = h.replace('#',''); if (h.length === 3) h = [...h].map(c => c + c).join(''); return [0,2,4].map(i => parseInt(h.slice(i, i+2), 16)); };
  const lum = c => { const [r,g,b] = rgb(c).map(x => { x /= 255; return x <= .03928 ? x/12.92 : Math.pow((x+.055)/1.055, 2.4); }); return .2126*r + .7152*g + .0722*b; };
  const cr = (a, b) => { const [x, y] = [lum(v(a)), lum(v(b))].sort((p, q) => q - p); return +((x + .05) / (y + .05)).toFixed(2); };
  return { theme: v('--ink'), 'text/panel': cr('--text','--panel'), 'muted/panel': cr('--muted','--panel'), 'muted/ink': cr('--muted','--ink'),
           'amber/panel': cr('--amber','--panel'), 'amber/ink': cr('--amber','--ink'), 'fillText/fill': cr('--on-fill','--amber-fill'),
           'deflt/panel': cr('--deflt','--panel'), 'rec/panel': cr('--rec','--panel') };
}"""
async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=EXE)
        ctx = await b.new_context(viewport={'width':1100,'height':950}, color_scheme='dark')
        page = await ctx.new_page(); page.on('pageerror', lambda e: errs.append(str(e)))
        await page.goto(URL); await page.evaluate(IMG)
        ink = lambda: page.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--ink').trim()")
        print('L1 Auto, system dark :', await ink())
        await page.emulate_media(color_scheme='light'); await page.wait_for_timeout(50)
        print('   Auto, system light:', await ink(), '(live, no reload)')
        print('L2 contrast LIGHT:', await page.evaluate(CONTRAST))
        await page.emulate_media(color_scheme='dark'); await page.wait_for_timeout(50)
        print('   contrast DARK :', await page.evaluate(CONTRAST))
        # override pinned against the system, persists across reload
        await page.evaluate("async () => { await loadFile(await makeImage(1600, 900, 'a.png')); }")
        await page.evaluate("() => { if (src) deselect(); }"); await page.locator('#btnMenu').click(); await page.locator('#appearance button[data-v=light]').click()
        print('L3 pinned Light while system dark:', await ink(), '| saved:', await page.evaluate("localStorage.getItem('dolly-appearance')"))
        await page.reload(); await page.wait_for_timeout(100)
        print('   after reload:', await ink(), '| button on:', await page.evaluate("() => document.querySelector('#appearance .on').dataset.v"))
        await page.evaluate("() => applyAppearance('dark')"); await page.emulate_media(color_scheme='light'); await page.wait_for_timeout(50)
        print('   pinned Dark while system light:', await ink())
        await page.evaluate("() => applyAppearance('auto')"); await page.wait_for_timeout(50)
        print('   back to Auto (system light):', await ink())

        # exports identical in both themes
        await page.evaluate(IMG)
        async def gif_hash(theme):
            await page.evaluate(f"""async () => {{ applyAppearance('{theme}'); await loadFile(await makeImage(800, 450, 'e.png'));
                shots.push(fitRect(300, 200, 240, 0.2)); refreshTotal(); $('outW').value = '480'; $('fps').value = 8; }}""")
            await page.locator('#btnExport').click(); await page.evaluate("() => $('btnGif').click()")
            await page.wait_for_function("() => document.querySelector('#media img') && !busy", timeout=60000)
            data = await page.evaluate("async () => Array.from(new Uint8Array(await (await (await fetch(document.querySelector('#dl a').href)).blob()).arrayBuffer()))")
            return hashlib.sha256(bytes(data)).hexdigest()[:16]
        hl, hd = await gif_hash('light'), await gif_hash('dark')
        print('L4 GIF export light vs dark:', hl, hd, 'IDENTICAL' if hl == hd else 'DIFFERENT')

        # screenshots in light mode
        await page.evaluate("() => applyAppearance('light')")
        await page.evaluate("() => { shots.push(fitRect(1100*0.5, 300, 260, 0)); refreshTotal(); selectLink(0); }")
        await page.screenshot(path=OUT + '/light_desk.png')
        m = await b.new_page(viewport={'width':390,'height':844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='light')
        m.on('pageerror', lambda e: errs.append('m: ' + str(e)))
        await m.goto(URL); await m.evaluate(IMG)
        await m.evaluate("() => applyAppearance('auto')")
        await m.evaluate("async () => { await loadFile(await makeImage(1600, 900, 'a.png')); shots.push(fitRect(500,300,400,0), fitRect(1200,600,300,0.3)); refreshTotal(); selectShot(1); }")
        await m.wait_for_timeout(100)
        await m.screenshot(path=OUT + '/light_mobile.png', full_page=True)
        await m.keyboard.press('Escape'); await m.evaluate("() => { if (src) deselect(); }"); await m.locator('#btnMenu').click(); await m.wait_for_timeout(250)
        await m.screenshot(path=OUT + '/light_sheet.png')
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
