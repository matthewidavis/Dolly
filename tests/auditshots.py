from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio
from playwright.async_api import async_playwright
VSETUP = open('videotest.py').read().split('SETUP = r"""')[1].split('"""')[0]
AUD = open('soundtest.py').read().split('AUD = r"""')[1].split('"""')[0]
IMG = r"""
window.photo = async (W = 1600, H = 1000) => {             // a photo-like test image: sky, hills, a house
  const c = document.createElement('canvas'); c.width = W; c.height = H; const g = c.getContext('2d');
  let gr = g.createLinearGradient(0, 0, 0, H * .6); gr.addColorStop(0, '#6aa8d8'); gr.addColorStop(1, '#f3d9a6'); g.fillStyle = gr; g.fillRect(0, 0, W, H);
  g.fillStyle = '#4f7a3a'; g.beginPath(); g.moveTo(0, H*.62); for (let x = 0; x <= W; x += 40) g.lineTo(x, H*.6 + Math.sin(x/170)*40); g.lineTo(W, H); g.lineTo(0, H); g.fill();
  g.fillStyle = '#3c5f2c'; g.beginPath(); g.moveTo(0, H*.75); for (let x = 0; x <= W; x += 40) g.lineTo(x, H*.74 + Math.sin(x/90+1)*30); g.lineTo(W, H); g.lineTo(0, H); g.fill();
  g.fillStyle = '#b8513a'; g.fillRect(W*.58, H*.5, W*.12, H*.13); g.fillStyle = '#7a2e22'; g.beginPath(); g.moveTo(W*.56, H*.5); g.lineTo(W*.64, H*.42); g.lineTo(W*.72, H*.5); g.fill();
  g.fillStyle = '#fff8'; g.beginPath(); g.arc(W*.2, H*.18, 60, 0, 7); g.fill();
  return new File([await new Promise(r => c.toBlob(r, 'image/jpeg', .9))], 'farm.jpg', { type: 'image/jpeg' });
};
true;
"""
async def shot(m, name, full=False): await m.wait_for_timeout(250); await m.screenshot(path=f'{OUT}/audit_{name}.png', full_page=full)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROMIUM)
        m = await b.new_page(viewport={'width':390,'height':844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await m.goto(URL); await m.evaluate(IMG); await m.evaluate(VSETUP); await m.evaluate(AUD)
        await shot(m, '01_firstrun')
        await m.evaluate("async () => { await loadFile(await photo()); shots.push(fitRect(1050, 470, 380, 0), fitRect(330, 300, 520, -0.08)); refreshTotal(); }")
        await shot(m, '02_loaded')
        await m.evaluate("() => selectShot(1)"); await shot(m, '03_shot_inspector')
        await m.evaluate("() => { window.scrollTo(0, 2000); }"); await shot(m, '04_shot_inspector_scrolled')
        await m.evaluate("() => { window.scrollTo(0, 0); selectLink(1); }"); await shot(m, '05_link_inspector_full', True)
        await m.evaluate("() => deselect()")
        await m.locator('#btnExport').click(); await shot(m, '06_export_sheet'); await m.keyboard.press('Escape')
        await m.locator('#btnDefaults').click(); await shot(m, '07_defaults_sheet'); await m.keyboard.press('Escape')
        await m.locator('#btnProject').click(); await shot(m, '08_project_sheet'); await m.keyboard.press('Escape')
        await m.evaluate("async () => { await loadFile(await makeClipWithSound()); }")
        await m.wait_for_function("() => src && src.audio")
        await m.evaluate("async () => { shots.push(fitRect(100, 60, 150, 0)); addFull(); refreshTotal(); await addTrack(makeWav(3, 880)); selectMedia(); }")
        await shot(m, '09_media_inspector_full', True)
        await m.evaluate("() => { window.scrollTo(0,0); selectSound(); }"); await shot(m, '10_sound_inspector_full', True)
        await b.close()
        b = await p.chromium.launch(executable_path=CHROMIUM)
        d = await b.new_page(viewport={'width':1280,'height':860})
        await d.goto(URL); await d.evaluate(IMG)
        await d.evaluate("async () => { await loadFile(await photo()); shots.push(fitRect(1050, 470, 380, 0), fitRect(330, 300, 520, -0.08)); refreshTotal(); selectShot(1); }")
        await shot(d, '11_desktop')
        await b.close()
asyncio.run(main())
