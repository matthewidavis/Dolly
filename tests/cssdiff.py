from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio
from playwright.async_api import async_playwright
from PIL import Image, ImageChops
IMG = open('auditshots.py').read().split('IMG = r"""')[1].split('"""')[0]
SETUP = "() => { setTimeout(async () => { await loadFile(await photo()); shots.push(fitRect(1050, 470, 380, 0.1), fitRect(330, 300, 520, 0)); deselect(); document.getElementById('status').classList.remove('show'); window.__a = 1; }, 0); }"
STATES = [('main', "() => {}"), ('shot', "() => { selectShot(1); }"), ('move', "() => { deselect(); selectLink(1); }"),
          ('timing', "() => { deselect(); selectTiming(); }"), ('projects', "() => { deselect(); openJobs(); }"), ('export', "() => { document.getElementById('dlgJobs').close(); $('btnExport').click(); }")]
async def shots_for(p, url, tag, vp):
    b = await p.chromium.launch(executable_path=CHROMIUM)
    kw = dict(viewport=vp[0], device_scale_factor=vp[1], is_mobile=vp[2], has_touch=vp[2])
    m = await b.new_page(**kw); await m.goto(url); await m.evaluate(IMG); await m.evaluate(SETUP); await m.wait_for_function("() => window.__a"); await m.wait_for_timeout(300)
    for name, js in STATES:
        await m.evaluate(js); await m.wait_for_timeout(300)
        await m.evaluate("() => document.getElementById('status').classList.remove('show')"); await m.wait_for_timeout(150)
        await m.screenshot(path=f'{OUT}/cd_{tag}_{name}.png')
    await b.close()
async def main():
    async with async_playwright() as p:
        for vpn, vp in [('phone', ({'width':390,'height':844}, 2, True)), ('desk', ({'width':1280,'height':820}, 1, False))]:
            await shots_for(p, REFERENCE_URL, 'old_' + vpn, vp)
            await shots_for(p, URL, 'new_' + vpn, vp)
            for name, _ in STATES:
                a = Image.open(f'{OUT}/cd_old_{vpn}_{name}.png').convert('RGB'); b = Image.open(f'{OUT}/cd_new_{vpn}_{name}.png').convert('RGB')
                d = ImageChops.difference(a, b); bbox = d.getbbox()
                n = sum(1 for px in d.getdata() if max(px) > 24)
                print(f'{vpn:5s} {name:9s} pixels that differ: {n:7d}  region: {bbox}')
asyncio.run(main())
