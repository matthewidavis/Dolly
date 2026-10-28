from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio, json, math
from playwright.async_api import async_playwright
IMG = open('auditshots.py').read().split('IMG = r"""')[1].split('"""')[0]
async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROMIUM)
        page = await b.new_page(viewport={'width':1100,'height':900}); page.on('pageerror', lambda e: errs.append(str(e)))
        await page.goto(URL); await page.evaluate(IMG)
        await page.evaluate("() => { setTimeout(async () => { await loadFile(await photo()); shots.splice(0); shots.push(fitRect(250, 300, 300, 0), fitRect(650, 700, 300, 0), fitRect(1050, 300, 300, 0), fitRect(1400, 700, 260, 0)); $('hold').value = 1; $('dur').value = 2; $('handheld').value = 'off'; refreshTotal(); window.__a = 1; }, 0); }")
        await page.wait_for_function("() => window.__a")
        CORNER = """(shape) => { $('pathShape').value = shape; refreshTotal(); const tl = buildTimeline(), mv = tl.segs.filter(s => s.kind === 'move');
            const pos = (sg, f) => ctr(cameraCrop(sg.t0 + sg.dur * f, tl));
            const ang = (a, b) => Math.atan2(b.cy - a.cy, b.cx - a.cx);
            const res = [];
            for (let k = 0; k < mv.length - 1; k++){
              const inA = ang(pos(mv[k], 0.97), pos(mv[k], 0.999)), outA = ang(pos(mv[k + 1], 0.001), pos(mv[k + 1], 0.03));
              let d = Math.abs(outA - inA) * 180 / Math.PI; res.push(+Math.min(d, 360 - d).toFixed(0)); }
            const h = tl.spans.filter(s => s.type === 'shot'), still = h.every(sp => { const a = ctr(cameraCrop(sp.t0 + sp.dur * 0.3, tl)), c = ctr(cameraCrop(sp.t0 + sp.dur * 0.7, tl)); return Math.hypot(a.cx - c.cx, a.cy - c.cy) < 0.5; });
            const exact = mv.every(sg => { const e = cameraCrop(sg.t0 + sg.dur - 1e-6, tl); return Math.hypot(ctr(e).cx - ctr(sg.b).cx, ctr(e).cy - ctr(sg.b).cy) < 0.5; });
            return { turnAtShotsDeg: res, stillDuringHolds: still, landsExactly: exact }; }"""
        await page.evaluate(f"() => {{ window.CORNER = {CORNER}; }}")
        print('C1 straight:', await page.evaluate("() => CORNER('straight')"))
        print('   curved:  ', await page.evaluate("() => CORNER('strong')"))
        # C2 arc overrides the curve on its move
        r = await page.evaluate("""() => { $('pathShape').value = 'strong'; setOut(1, 'arc', 'left'); refreshTotal(); const tl = buildTimeline(), sg = tl.segs.filter(s => s.kind === 'move')[1];
            const m = cameraCrop(sg.t0 + sg.dur * 0.5, tl), f = sg.ease(0.5), A = ctr(sg.a), B = ctr(sg.b), len = Math.hypot(B.cx - A.cx, B.cy - A.cy);
            const lineX = A.cx + (B.cx - A.cx) * f, lineY = A.cy + (B.cy - A.cy) * f, off = Math.hypot(ctr(m).cx - lineX, ctr(m).cy - lineY);
            delete shots[1].out; refreshTotal(); return { arcBendPctOfLength: +(off / len * 100).toFixed(1) }; }""")
        print('C2 Arc left on a curved-path move bends by', r['arcBendPctOfLength'], '% of its length (Arc sets 20%)')
        # C3 persistence
        r = await page.evaluate("""async () => { $('pathShape').value = 'straight'; refreshTotal(); await Promise.resolve(); const p = await buildProject(false);
            $('pathShape').value = 'strong'; refreshTotal(); await Promise.resolve(); undo(); const afterUndo = $('pathShape').value;
            $('pathShape').value = 'strong'; applyProject(p, { quiet: true }); return [p.defaults.shape, afterUndo, $('pathShape').value]; }""")
        print('C3 project file keeps "straight":', r[0], '| undo restores it:', r[1], '| loading the file restores it:', r[2])
        await page.evaluate("() => { $('pathShape').value = 'strong'; refreshTotal(); }")
        paths = await page.evaluate("""() => { const tr = shape => { $('pathShape').value = shape; refreshTotal(); const tl = buildTimeline(), out = [];
            for (let k = 0; k <= 400; k++){ const c = ctr(cameraCrop(tl.total * k / 400, tl)); out.push([c.cx, c.cy]); } return out; };
            return { straight: tr('straight'), curved: tr('curved'), shots: shots.map(s => [ctr(s).cx, ctr(s).cy]) }; }""")
        json.dump(paths, open(OUT + '/curvepaths.json', 'w'))
        await b.close()
        # D finger drawing on a phone
        b = await p.chromium.launch(executable_path=CHROMIUM)
        ctx = await b.new_context(viewport={'width':390,'height':844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        m = await ctx.new_page(); m.on('pageerror', lambda e: errs.append(str(e)))
        cdp = await ctx.new_cdp_session(m)
        await m.goto(URL); await m.evaluate(IMG)
        await m.evaluate("() => { setTimeout(async () => { await loadFile(await photo()); deselect(); window.__a = 1; }, 0); }")
        await m.wait_for_function("() => window.__a"); await m.wait_for_timeout(300)
        g = await m.evaluate("() => { const r = vf.getBoundingClientRect(); return { l: r.left, t: r.top, k: r.width / vf.width * scale }; }")
        S = lambda ix, iy: (g['l'] + ix * g['k'], g['t'] + iy * g['k'])
        async def touch(kind, pts): await cdp.send('Input.dispatchTouchEvent', {'type': kind, 'touchPoints': [{'x': x, 'y': y} for (x, y) in pts]})
        a0, a1 = S(400, 250), S(900, 700)
        await touch('touchStart', [a0])
        for k in range(1, 11): await touch('touchMove', [(a0[0] + (a1[0] - a0[0]) * k / 10, a0[1] + (a1[1] - a0[1]) * k / 10)])
        await touch('touchEnd', [])
        r = await m.evaluate("() => { const s = shots[shots.length - 1]; return { shots: shots.length, active: activeShot, x: Math.round(s.x), y: Math.round(s.y), aspect: +(s.w / s.h).toFixed(3), frame: +(src.w / src.h).toFixed(3) }; }")
        print('D1 finger drag on the image draws shot 2 from where the finger landed:', r)
        await touch('touchStart', [S(1450, 930)]); await touch('touchEnd', [])
        print('D2 a tap on empty image adds nothing:', await m.evaluate("() => shots.length"), 'shots, selection', await m.evaluate("() => activeShot"))
        await m.screenshot(path=OUT + '/curve_draw.png')
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
