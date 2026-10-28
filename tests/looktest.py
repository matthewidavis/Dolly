from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio
from playwright.async_api import async_playwright
IMG = open('auditshots.py').read().split('IMG = r"""')[1].split('"""')[0]
STATS = """(tl, t, W = 320, H = 200) => { const c = document.createElement('canvas'); c.width = W; c.height = H; const g = c.getContext('2d'); renderAtTime(g, W, H, t, tl, 30);
  const d = g.getImageData(0, 0, W, H).data; let r = 0, gg = 0, b = 0, minL = 255, sat = 0, n = 0;
  for (let i = 0; i < d.length; i += 4){ r += d[i]; gg += d[i+1]; b += d[i+2]; const l = 0.2126*d[i] + 0.7152*d[i+1] + 0.0722*d[i+2]; minL = Math.min(minL, l); sat += Math.max(d[i], d[i+1], d[i+2]) - Math.min(d[i], d[i+1], d[i+2]); n++; }
  const px = (x, y) => { const i = (y * W + x) * 4; return [d[i], d[i+1], d[i+2]]; };
  return { mean: [Math.round(r/n), Math.round(gg/n), Math.round(b/n)], minL: Math.round(minL), sat: Math.round(sat / n), corner: px(3, 3), centre: px(W >> 1, H >> 1), top: px(W >> 1, 2), data: Array.from(d.slice(0, 4000)) }; }"""
async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROMIUM)
        page = await b.new_page(viewport={'width':1100,'height':900}); page.on('pageerror', lambda e: errs.append(str(e)))
        page.on('console', lambda c: errs.append('console: ' + c.text) if c.type == 'warning' and 'Look' in c.text else None)
        await page.goto(URL); await page.evaluate(IMG)
        await page.evaluate("() => { setTimeout(async () => { await loadFile(await photo()); shots.push(fitRect(800, 500, 900, 0)); refreshTotal(); window.__a = 1; }, 0); }")
        await page.wait_for_function("() => window.__a")
        await page.evaluate(f"() => {{ window.STATS = {STATS}; window.T = () => buildTimeline(); window.MID = () => buildTimeline().spans[0].t0 + 0.1; }}")
        base = await page.evaluate("() => STATS(T(), MID())")
        plain = await page.evaluate("() => STATS({ ...T(), look: null }, MID())")
        print('L1 no look = the plain render:', base['data'] == plain['data'], '| WebGL available:', await page.evaluate("() => !!lookPipeline()"))
        res = {}
        for k in ['warm', 'teal', 'night', 'faded', 'bw']:
            r = await page.evaluate(f"() => {{ $('lookPreset').value = '{k}'; $('lookStrength').value = 100; refreshTotal(); const s = STATS(T(), MID()); return s; }}")
            res[k] = r
        bm = base['mean']
        print('L2 mean RGB  none', bm, '| sat', base['sat'], '| darkest', base['minL'])
        for k, r in res.items(): print(f'   {k:6s} mean {r["mean"]} sat {r["sat"]:3d} darkest {r["minL"]:3d}')
        checks = {'warm: redder vs blue': res['warm']['mean'][0] - res['warm']['mean'][2] > bm[0] - bm[2],
                  'night: bluer and darker': res['night']['mean'][2] - res['night']['mean'][0] > bm[2] - bm[0] and sum(res['night']['mean']) < sum(bm),
                  'faded: lifted blacks, less colour': res['faded']['minL'] > base['minL'] + 10 and res['faded']['sat'] < base['sat'],
                  'b&w: no colour': res['bw']['sat'] <= 2, 'teal: a real change': res['teal']['mean'] != bm}
        print('   checks:', checks)
        r = await page.evaluate("""() => { $('lookPreset').value = 'night'; $('lookStrength').value = 0; refreshTotal(); const z = STATS(T(), MID());
            $('lookStrength').value = 50; refreshTotal(); const h = STATS(T(), MID()); $('lookStrength').value = 100; refreshTotal(); const f = STATS(T(), MID()); return [z.mean, h.mean, f.mean]; }""")
        print('L3 Cool night at 0% / 50% / 100%:', r, '| 0% equals none:', r[0] == bm)
        r = await page.evaluate("""() => { $('lookPreset').value = 'none'; $('lookGrain').value = 'heavy'; refreshTotal(); const tl = T(), t = MID();
            const a = STATS(tl, t).data, a2 = STATS(tl, t).data, b = STATS(tl, t + 1 / 30).data;
            $('lookGrain').value = 'off'; $('lookVig').value = 'strong'; refreshTotal(); const v = STATS(T(), t);
            $('lookVig').value = 'off'; $('lookBars').value = 'on'; refreshTotal(); const cb = STATS(T(), t, 320, 200);
            $('lookBars').value = 'off'; refreshTotal();
            return { grainSameFrameSame: a.join() === a2.join(), grainNextFrameDiffers: a.join() !== b.join(), vigCorner: v.corner, vigCentre: v.centre, plainCorner: STATS(T(), t).corner, barsTop: cb.top }; }""")
        print('L4 grain repeatable per frame:', r['grainSameFrameSame'], '| changes between frames:', r['grainNextFrameDiffers'], '| vignette corner', r['vigCorner'], 'vs plain', r['plainCorner'], '| cinema bars top pixel', r['barsTop'])
        bars = await page.evaluate("""() => { $('lookBars').value = 'on'; refreshTotal(); const W = 320, H = 200, c = document.createElement('canvas'); c.width = W; c.height = H; const g = c.getContext('2d');
            renderAtTime(g, W, H, MID(), T(), 30); const d = g.getImageData(0, 0, W, H).data; let rows = 0; for (let y = 0; y < H; y++){ const i = (y * W + 160) * 4; if (d[i] + d[i+1] + d[i+2] === 0) rows++; }
            $('lookBars').value = 'off'; refreshTotal(); return { blackRows: rows, expected: H - Math.round(W / 2.39) }; }""")
        print('   cinema bars black rows:', bars)
        # L5 an export matches the preview render
        r = await page.evaluate("""async () => { $('lookPreset').value = 'teal'; $('lookStrength').value = 90; $('lookVig').value = 'soft'; $('outW').value = '480'; $('fps').value = 10; refreshTotal();
            const ref = T(); enqueueExport('gif'); const j = jobs[jobs.length - 1];
            await new Promise(res => { const c = setInterval(() => { if (j.state === 'done' || j.state === 'failed'){ clearInterval(c); res(); } }, 50); });
            const gg = await decodeGif(new Uint8Array(await j.blob.arrayBuffer())); const f = 4, got = gg.frames[f].canvas.getContext('2d').getImageData(0, 0, gg.width, gg.height).data;
            const c = document.createElement('canvas'); c.width = gg.width; c.height = gg.height; renderAtTime(c.getContext('2d'), gg.width, gg.height, f / 10, ref, 10);
            const want = c.getContext('2d').getImageData(0, 0, gg.width, gg.height).data; let e = 0; for (let i = 0; i < want.length; i += 4) e += Math.abs(want[i] - got[i]) + Math.abs(want[i+1] - got[i+1]) + Math.abs(want[i+2] - got[i+2]);
            return { state: j.state, meanErrPerChannel: +(e / (want.length / 4) / 3).toFixed(2) }; }""")
        print('L5 graded GIF export vs preview render:', r, '(GIF colour rounding only)')
        # L6 persistence
        r = await page.evaluate("""async () => { await Promise.resolve(); const p = await buildProject(false); $('lookPreset').value = 'none'; $('lookVig').value = 'off'; applyProject(p, { quiet: true });
            const fromFile = [$('lookPreset').value, $('lookStrength').value, $('lookVig').value];
            $('lookPreset').value = 'bw'; refreshTotal(); await Promise.resolve(); undo(); return { file: [p.defaults.look, p.defaults.lookStrength, p.defaults.vig], fromFile, afterUndo: $('lookPreset').value }; }""")
        print('L6 project keeps', r['file'], '| loads back', r['fromFile'], '| undo after switching to B&W:', r['afterUndo'])
        # L7 cost per 1280x720 frame
        r = await page.evaluate("""() => { const W = 1280, H = 720, c = document.createElement('canvas'); c.width = W; c.height = H; const g = c.getContext('2d'), out = {};
            for (const on of [false, true]){ $('lookPreset').value = on ? 'teal' : 'none'; $('lookGrain').value = on ? 'fine' : 'off'; $('lookVig').value = on ? 'soft' : 'off'; refreshTotal(); const tl = T();
              renderAtTime(g, W, H, MID(), tl, 30); const t0 = performance.now(); for (let k = 0; k < 20; k++) renderAtTime(g, W, H, MID() + k / 30, tl, 30); g.getImageData(0, 0, 1, 1); out[on ? 'withLook' : 'plain'] = +((performance.now() - t0) / 20).toFixed(1); }
            return out; }""")
        print('L7 ms per 1280x720 frame:', r)
        await b.close()
        # L8 phone: Look panel shows the finished frame
        b = await p.chromium.launch(executable_path=CHROMIUM)
        m = await b.new_page(viewport={'width':390,'height':844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        await m.goto(URL); await m.evaluate(IMG)
        await m.evaluate("() => { setTimeout(async () => { await loadFile(await photo()); shots.push(fitRect(1050, 470, 400, 0)); deselect(); document.getElementById('status').classList.remove('show'); window.__a = 1; }, 0); }")
        await m.wait_for_function("() => window.__a"); await m.wait_for_timeout(200)
        await m.locator('#trayLook').tap(); await m.wait_for_timeout(200)
        await m.evaluate("() => { document.getElementById('lookSeg').closest('details').open = true; }"); await m.wait_for_timeout(60); await m.locator('#lookSeg button[data-v="teal"]').tap(); await m.evaluate("() => { document.getElementById('vigSeg').closest('details').open = true; }"); await m.wait_for_timeout(60); await m.locator('#vigSeg button[data-v="soft"]').tap(); await m.evaluate("() => { document.getElementById('grainSeg').closest('details').open = true; }"); await m.wait_for_timeout(60); await m.locator('#grainSeg button[data-v="fine"]').tap(); await m.evaluate("() => { document.getElementById('cineSeg').closest('details').open = true; }"); await m.wait_for_timeout(60); await m.locator('#cineSeg button[data-v="on"]').tap()
        await m.wait_for_timeout(250)
        await m.evaluate("() => { document.getElementById('inspector').scrollTop = 330; }"); await m.wait_for_timeout(150)
        await m.screenshot(path=OUT + '/look_panel.png')
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
