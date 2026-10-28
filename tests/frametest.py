from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio
from playwright.async_api import async_playwright
IMG = open('auditshots.py').read().split('IMG = r"""')[1].split('"""')[0]
async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROMIUM)
        m = await b.new_page(viewport={'width':390,'height':844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        m.on('pageerror', lambda e: errs.append(str(e)))
        await m.goto(URL); await m.evaluate(IMG)
        await m.evaluate("() => { setTimeout(async () => { await loadFile(await photo()); shots.push(fitRect(1050, 470, 400, 0), fitRect(400, 500, 600, 0.1)); deselect(); document.getElementById('status').classList.remove('show'); window.__a = 1; }, 0); }")
        await m.wait_for_function("() => window.__a"); await m.wait_for_timeout(200)
        before = await m.evaluate("() => ({ ar: +ar.toFixed(4), full: [shots[0].w, shots[0].h], s1c: [Math.round(ctr(shots[1]).cx), Math.round(ctr(shots[1]).cy)], area1: Math.round(shots[1].w * shots[1].h), size: settings() })")
        print('F0 Original frame:', before)
        # F1 Fill 9:16 through the Look panel
        await m.locator('#trayLook').tap(); await m.wait_for_timeout(250)
        await m.evaluate("() => { document.getElementById('frameSeg').closest('details').open = true; }"); await m.wait_for_timeout(60); await m.locator('#frameSeg button[data-v="9:16"]').tap(); await m.wait_for_timeout(200)
        r = await m.evaluate("""() => ({ ar: +ar.toFixed(4), full: [Math.round(shots[0].w), Math.round(shots[0].h), Math.round(ctr(shots[0]).cx)], shotAspects: shots.map(s => +(s.w / s.h).toFixed(4)),
            s1c: [Math.round(ctr(shots[1]).cx), Math.round(ctr(shots[1]).cy)], area1: Math.round(shots[1].w * shots[1].h), size: settings(), fitVisible: !$('fitSeg').hidden, note: $('frameNote').textContent.slice(0, 40) })""")
        print('F1 Fill 9:16:', r)
        await m.screenshot(path=OUT + '/frame_panel.png')
        # export a frame: right size, picture fills it
        sz = await m.evaluate("""async () => { $('outW').value = '480'; $('fps').value = 10; refreshTotal(); enqueueExport('gif'); const j = jobs[jobs.length - 1];
            await new Promise(r => { const c = setInterval(() => { if (j.state === 'done' || j.state === 'failed'){ clearInterval(c); r(); } }, 50); });
            const g = await decodeGif(new Uint8Array(await j.blob.arrayBuffer())); const f = g.frames[5].canvas.getContext('2d').getImageData(0, 0, g.width, g.height).data;
            const px = (x, y) => { const i = (y * g.width + x) * 4; return f[i] + f[i + 1] + f[i + 2]; };
            return { w: g.width, h: g.height, cornersNotBlack: [px(2, 2), px(g.width - 3, g.height - 3)].every(v => v > 30) }; }""")
        print('   export:', sz, '| expected about 9:16 and filled to the edges')
        # F2 Fit with bars (blurred), then black
        await m.evaluate("() => { document.getElementById('fitSeg').closest('details').open = true; }"); await m.wait_for_timeout(60); await m.locator('#fitSeg button[data-v="bars"]').tap(); await m.wait_for_timeout(200)
        r = await m.evaluate("() => ({ ar: +ar.toFixed(4), shotAspect: +(shots[1].w / shots[1].h).toFixed(4), size: settings(), bgVisible: !$('bgSeg').hidden })")
        print('F2 Fit with bars:', r)
        for bg in ['black', 'blur']:
            await m.locator(f'#bgSeg button[data-v="{bg}"]').tap(); await m.wait_for_timeout(150)
            out = await m.evaluate("""() => { const tl = buildTimeline(), S = settings(), c = document.createElement('canvas'); c.width = S.W; c.height = S.H; const g = c.getContext('2d');
                renderAtTime(g, S.W, S.H, tl.spans[2].t0 + 0.05, tl, 10); const d = g.getImageData(0, 0, S.W, S.H).data; const px = (x, y) => { const i = (y * S.W + x) * 4; return [d[i], d[i+1], d[i+2]]; };
                return { size: [S.W, S.H], topBar: px(S.W >> 1, 3), middle: px(S.W >> 1, S.H >> 1) }; }""")
            print(f'   {bg:5s} bars:', out)
        # F3 the viewfinder shows the output's shape during playback
        await m.locator('#inspector .done-btn').tap(); await m.wait_for_timeout(150)
        await m.locator('#btnPreview').tap(); await m.wait_for_timeout(500)
        v = await m.evaluate("() => { const d = vctx.getImageData(0, 0, vf.width, vf.height).data, W = vf.width, H = vf.height; const px = (x, y) => { const i = (y * W + x) * 4; return d[i] + d[i+1] + d[i+2]; }; return { leftEdgeBlack: px(2, H >> 1) === 0, centreLit: px(W >> 1, H >> 1) > 30 }; }")
        await m.screenshot(path=OUT + '/frame_play.png')
        await m.locator('#btnPreview').tap()
        print('F3 playback in the viewfinder shows the 9:16 frame centred with bars beside it:', v)
        # F4 undo restores the previous frame and shot shapes; project files keep it
        r = await m.evaluate("""async () => { while (undoStack.length && $('frameShape').value !== 'original') undo();
            const back = { frame: $('frameShape').value, ar: +ar.toFixed(4), aspect: +(shots[1].w / shots[1].h).toFixed(4) };
            redo(); redo(); const p = await buildProject(false); $('frameShape').value = 'original'; $('frameFit').value = 'fill'; applyFrameAspect(true); refreshTotal();
            applyProject(p, { quiet: true }); return { back, file: [p.defaults.frame, p.defaults.fit, p.defaults.bg], afterLoad: [$('frameShape').value, $('frameFit').value, +ar.toFixed(4)] }; }""")
        print('F4 undo back to Original:', r['back'], '| project keeps', r['file'], '| loading restores', r['afterLoad'])
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
