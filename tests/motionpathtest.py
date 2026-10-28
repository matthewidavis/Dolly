from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio
from playwright.async_api import async_playwright
PIMG = open('projtest.py').read().split('IMG = r"""')[1].split('"""')[0]
STRIPES = r"""
window.stripes = async () => {   // fine vertical/horizontal detail so blur is measurable
  const c = document.createElement('canvas'); c.width = 1600; c.height = 1000; const g = c.getContext('2d');
  g.fillStyle = '#222'; g.fillRect(0, 0, 1600, 1000);
  for (let x = 0; x < 1600; x += 8){ g.fillStyle = (x / 8) % 2 ? '#eee' : '#333'; g.fillRect(x, 0, 4, 1000); }
  for (let y = 0; y < 1000; y += 40){ g.fillStyle = 'rgba(240,180,60,.6)'; g.fillRect(0, y, 1600, 6); }
  return new File([await new Promise(r => c.toBlob(r, 'image/png'))], 'stripes.png', { type: 'image/png' });
};
window.sharpness = (tl, t, W = 320, H = 200) => {     // mean absolute horizontal gradient of the rendered frame
  const c = document.createElement('canvas'); c.width = W; c.height = H; const g = c.getContext('2d');
  renderAtTime(g, W, H, t, tl, 30); const d = g.getImageData(0, 0, W, H).data; let s = 0, n = 0;
  for (let y = 0; y < H; y += 2) for (let x = 1; x < W; x++){ const i = (y * W + x) * 4; s += Math.abs(d[i] - d[i - 4]); n++; }
  return +(s / n).toFixed(2);
};
true;
"""
async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROMIUM)
        page = await b.new_page(viewport={'width':1100,'height':900}); page.on('pageerror', lambda e: errs.append(str(e)))
        await page.goto(URL); await page.evaluate(PIMG); await page.evaluate(STRIPES)
        await page.evaluate("() => { setTimeout(async () => { await loadFile(await stripes()); window.__a = 1; }, 0); }")
        await page.wait_for_function("() => window.__a")
        # P1 endpoints exact, every path
        r = await page.evaluate("""() => { const a = fitRect(300, 300, 300, 0.1), b = fitRect(1300, 700, 220, -0.2), out = {};
            for (const pth of ['direct', 'natural', 'sweep']) { const s = cropBetween(a, b, 0, pth), e = cropBetween(a, b, 1, pth);
              out[pth] = Math.max(Math.abs(s.x - a.x), Math.abs(s.w - a.w), Math.abs(e.x - b.x), Math.abs(e.w - b.w)) < 1e-6; } return out; }""")
        print('P1 every path starts and ends exactly on its shots:', r)
        # P2 direct: a zoom keeps its fixed point; no pull-back
        r = await page.evaluate("""() => { const a = fitRect(800, 500, 1200, 0), b = fitRect(1100, 650, 300, 0);
            // the fixed point P has the same relative position inside every frame
            const rel = c => [((1100 + (1100-800) * 300 / (1200-300)) - c.x) / c.w];
            const P = { x: 800 + (1100 - 800) * 1200 / (1200 - 300), y: 500 + (650 - 500) * 1200 / (1200 - 300) };
            const fr = [0, .25, .5, .75, 1].map(t => { const c = cropBetween(a, b, t, 'direct'); return [+((P.x - c.x) / c.w).toFixed(4), +((P.y - c.y) / c.h).toFixed(4), Math.round(c.w)]; });
            return fr; }""")
        print('P2 direct zoom: fixed point stays at the same spot in frame:', len(set((x, y) for x, y, _ in r)) == 1, r)
        # P3 pull-back on long moves; sweep > natural > direct; never past the full frame
        r = await page.evaluate("""() => { const a = fitRect(250, 250, 300, 0), b = fitRect(1350, 750, 300, 0), o = {};
            for (const pth of ['direct', 'natural', 'sweep']) o[pth] = Math.round(Math.max(...[...Array(21).keys()].map(k => cropBetween(a, b, k / 20, pth).w)));
            const c = fitRect(150, 150, 150, 0), d = fitRect(1450, 850, 150, 0);
            o.sweepFarCap = Math.round(Math.max(...[...Array(21).keys()].map(k => cropBetween(c, d, k / 20, 'sweep').w)));
            return o; }""")
        print('P3 widest frame mid-move (shots 300px wide, far apart):', r, '| image width 1600')
        # P4 motion blur: fast move softer, hold untouched
        await page.evaluate("() => { shots.push(fitRect(300, 400, 400, 0), fitRect(1300, 600, 400, 0)); $('dur').value = 0.8; $('camPath').value = 'direct'; refreshTotal(); }")
        r = await page.evaluate("""() => { const res = {};
            for (const bl of ['off', 'natural', 'strong']){ $('camBlur').value = bl; const tl = buildTimeline();
              const mid = tl.spans[3].t0 + tl.spans[3].dur / 2, hold = tl.spans[2].t0 + tl.spans[2].dur / 2;
              res[bl] = { fastMove: sharpness(tl, mid), hold: sharpness(tl, hold), samples: camBlurCount(mid, tl, 320, 30, false, 1) }; }
            $('camBlur').value = 'natural'; return res; }""")
        print('P4 sharpness (higher = crisper):', r)
        # P5 settings: Timing panel, undo, project file, export snapshot
        await page.evaluate("() => { refreshTotal(); selectTiming(); }")
        await page.evaluate("() => { document.getElementById('pathSeg').closest('details').open = true; }"); await page.wait_for_timeout(60); await page.locator('#pathSeg button[data-v=sweep]').click(); await page.evaluate("() => { document.getElementById('blurSeg').closest('details').open = true; }"); await page.wait_for_timeout(60); await page.locator('#blurSeg button[data-v=strong]').click()
        st = await page.evaluate("() => [$('camPath').value, $('camBlur').value, $('pathNote').textContent.slice(0, 40)]")
        await page.keyboard.press('Control+z'); await page.wait_for_timeout(50)
        u = await page.evaluate("() => [$('camPath').value, $('camBlur').value]")
        await page.keyboard.press('Control+Shift+z'); await page.wait_for_timeout(50)
        proj = await page.evaluate("async () => { const p = await buildProject(false); $('camPath').value = 'direct'; $('camBlur').value = 'off'; applyProject(p); return [p.defaults.path, p.defaults.blur, $('camPath').value, $('camBlur').value]; }")
        print('P5 Timing panel sets:', st, '| undo:', u, '| project file round trip:', proj)
        snap = await page.evaluate("""async () => { $('outW').value = '480'; $('fps').value = 30; $('camBlur').value = 'strong'; refreshTotal();
            const ref = buildTimeline(); enqueueExport('gif'); const job = jobs[jobs.length - 1];
            $('camBlur').value = 'off'; $('camPath').value = 'direct'; refreshTotal();          // changed mid-export
            await new Promise(r => { const c = setInterval(() => { if (job.state === 'done'){ clearInterval(c); r(); } }, 50); });
            const g = await decodeGif(new Uint8Array(await job.blob.arrayBuffer()));
            const f = Math.round((ref.spans[3].t0 + ref.spans[3].dur / 2) * 30), got = g.frames[f].canvas.getContext('2d').getImageData(0, 0, g.width, g.height).data;
            const c = document.createElement('canvas'); c.width = g.width; c.height = g.height; const x = c.getContext('2d');
            renderAtTime(x, g.width, g.height, f / 30, ref, 30); const want = x.getImageData(0, 0, g.width, g.height).data;
            let e = 0; for (let i = 0; i < want.length; i += 4) e += Math.abs(want[i] - got[i]); return [job.tl.blur, job.tl.segs[1].path, +(e / (want.length / 4)).toFixed(2)]; }""")
        print('P6 export keeps its settings after a mid-export change: blur', snap[0], 'path', snap[1], '| mean error vs reference frame', snap[2], '(GIF quantisation only)')
        # P7 export cost of blur on a fast-move sequence
        t = await page.evaluate("""async () => { const out = {}; for (const bl of ['off', 'natural']){ $('camBlur').value = bl; $('outW').value = '720'; $('vidFmt').value = 'webm'; refreshTotal();
            const t0 = performance.now(); enqueueExport('webm'); const job = jobs[jobs.length - 1];
            await new Promise(r => { const c = setInterval(() => { if (job.state === 'done' || job.state === 'failed'){ clearInterval(c); r(); } }, 50); });
            out[bl] = +((performance.now() - t0) / 1000).toFixed(1); } return out; }""")
        print('P7 720px WebM export time (s), blur off vs natural:', t)
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
