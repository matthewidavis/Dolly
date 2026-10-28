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
        await m.evaluate("() => { setTimeout(async () => { await loadFile(await photo()); shots.push(fitRect(500, 450, 420, 0.05), fitRect(1150, 600, 380, 0)); $('hold').value = 2; deselect(); window.__a = 1; }, 0); }")
        await m.wait_for_function("() => window.__a")
        r = await m.evaluate("""() => { const out = {};
          for (const st of ['still', 'pushin', 'pushout', 'float']){
            $('holdStyle').value = st; $('handheld').value = 'off'; refreshTotal(); const tl = buildTimeline();
            const hs = tl.segs.find(s => s.kind === 'hold' && s.a === shots[1]), mv = tl.segs[tl.segs.indexOf(hs) + 1];
            const c0 = cameraCrop(hs.t0 + 1e-6, tl), c1 = cameraCrop(hs.t0 + hs.dur - 1e-4, tl), c2 = cameraCrop(mv.t0 + 1e-4, tl);
            const sh = shots[1], C = o => ctr(o);
            out[st] = { arrivesExact: Math.abs(c0.w - sh.w) < 0.01 && Math.abs(C(c0).cx - C(sh).cx) < 0.01,
                        endW: +(c1.w / sh.w).toFixed(3), endShift: +Math.hypot(C(c1).cx - C(sh).cx, C(c1).cy - C(sh).cy).toFixed(1),
                        jumpAtMove: +Math.max(Math.abs(c2.w - c1.w), Math.hypot(C(c2).cx - C(c1).cx, C(c2).cy - C(c1).cy)).toFixed(2) }; }
          return out; }""")
        for k, v in r.items(): print(f'L1-3 {k:8s}', v)
        # L4 handheld: small, smooth, inside, repeatable — also on the full frame
        r = await m.evaluate("""() => { $('holdStyle').value = 'still'; const res = {};
          for (const sk of ['subtle', 'strong']){ $('handheld').value = sk; refreshTotal(); const tl = buildTimeline();
            let maxOff = 0, maxStep = 0, inside = true, maxRot = 0, prev = null;
            for (let k = 0; k < 600; k++){ const t = k / 60, c = cameraCrop(t, tl); if (!c) continue;
              const base = cameraCrop(t, { ...tl, shake: 'off' }), d = Math.hypot(ctr(c).cx - ctr(base).cx, ctr(c).cy - ctr(base).cy) / base.w;
              maxOff = Math.max(maxOff, d); maxRot = Math.max(maxRot, Math.abs(rotOf(c) - rotOf(base)) * 180 / Math.PI);
              for (const [x, y] of cornersOf(c)) if (x < -0.01 || y < -0.01 || x > src.w + 0.01 || y > src.h + 0.01) inside = false;
              if (prev && k % 1 === 0 && t < tl.spans[1].t0) maxStep = Math.max(maxStep, Math.hypot(ctr(c).cx - ctr(prev).cx, ctr(c).cy - ctr(prev).cy) / c.w);
              prev = c; }
            const full = cameraCrop(0.3, tl), again = cameraCrop(0.3, tl);
            res[sk] = { maxOffsetPctOfWidth: +(maxOff * 100).toFixed(2), maxTiltDeg: +maxRot.toFixed(2), maxStepPerFramePct: +(maxStep * 100).toFixed(3),
                        insideImage: inside, fullFrameMoves: Math.abs(ctr(full).cx - src.w / 2) > 0.5 || Math.abs(ctr(full).cy - src.h / 2) > 0.5, repeatable: full.x === again.x && full.y === again.y }; }
          $('handheld').value = 'off'; refreshTotal(); return res; }""")
        for k, v in r.items(): print(f'L4 handheld {k:6s}', v)
        # L5 per-shot hold, undo, project round trip, export snapshot
        await m.evaluate("() => { selectShot(1); }"); await m.locator('#toolHold').tap(); await m.wait_for_timeout(150)
        await m.locator('#inspector .hold-chips button', has_text='Float').tap(); await m.wait_for_timeout(100)
        a = await m.evaluate("() => [shots[1].life, holdStyleOf(1), holdStyleOf(2)]")
        await m.screenshot(path=OUT + '/life_shot.png')
        await m.evaluate("() => undo()"); u = await m.evaluate("() => shots[1].life ?? null")
        await m.evaluate("() => redo()")
        pr = await m.evaluate("async () => { $('handheld').value = 'subtle'; $('holdStyle').value = 'pushin'; refreshTotal(); const p = await buildProject(false); $('handheld').value = 'off'; $('holdStyle').value = 'still'; delete shots[1].life; applyProject(p, { quiet: true }); return [p.defaults.life, p.defaults.shake, $('holdStyle').value, $('handheld').value, shots[1].life]; }")
        print('L5 shot 2 set to Float:', a, '| undo removes it:', u is None, '| project round trip:', pr)
        await m.evaluate("() => { deselect(); selectTiming(); }"); await m.wait_for_timeout(250)
        await m.evaluate("() => { document.getElementById('inspector').scrollTop = 260; }"); await m.wait_for_timeout(150)
        await m.screenshot(path=OUT + '/life_timing.png')
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
