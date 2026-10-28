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
        await m.evaluate("() => { setTimeout(async () => { await loadFile(await photo()); shots.push(fitRect(400, 400, 360, 0), fitRect(1200, 600, 360, 0)); deselect(); window.__a = 1; }, 0); }")
        await m.wait_for_function("() => window.__a"); await m.wait_for_timeout(200)
        # S1 default style from the Timing panel; the preview animates
        await m.locator('#trayTiming').tap(); await m.wait_for_timeout(300)
        print('S1 default style starts as:', await m.evaluate("() => [$('ease').value, $('easeNote').textContent]"))
        await m.evaluate("() => { document.getElementById('easeSeg').closest('details').open = true; }"); await m.wait_for_timeout(60); await m.locator('#easeSeg button[data-v=overshoot]').tap(); await m.wait_for_timeout(100)
        a = await m.evaluate("() => document.querySelector('#easePreviewSlot canvas').toDataURL()"); await m.wait_for_timeout(350)
        b2 = await m.evaluate("() => document.querySelector('#easePreviewSlot canvas').toDataURL()")
        print('   tapped Overshoot:', await m.evaluate("() => [$('ease').value, curTL.segs.find(s => s.kind === 'move').style]"), '| preview animating:', a != b2)
        await m.screenshot(path=OUT + '/style_timing.png')
        await m.locator('#inspector .done-btn').tap(); await m.wait_for_timeout(200)
        # S2 per-move style, custom marker, reset
        await m.evaluate("() => selectLink(1)"); await m.wait_for_timeout(250)
        await m.locator('#moveStyle').tap(); await m.wait_for_timeout(200)
        await m.locator('#inspector .style-chips button', has_text='Whip').tap(); await m.wait_for_timeout(150)
        s2 = await m.evaluate("() => [shots[1].out && shots[1].out.ease, document.querySelectorAll('.link')[1].classList.contains('custom'), effTrans(0).ease]")
        await m.screenshot(path=OUT + '/style_move.png')
        print('S2 move 2 set to Whip:', s2[0], '| marked custom:', s2[1], '| move 1 keeps the default:', s2[2])
        # S3 Overshoot passes the target, then lands exactly
        r = await m.evaluate("""() => { $('camPath').value = 'direct'; refreshTotal(); const tl = buildTimeline(), sg = tl.segs.find(s => s.kind === 'move' && s.style === 'overshoot' && s.a !== shots[0]) || tl.segs.filter(s => s.kind === 'move')[0];
            const target = ctr(sg.b).cx, start = ctr(sg.a).cx, dir = Math.sign(target - start); let peak = -Infinity;
            for (let k = 0; k <= 100; k++){ const c = ctr(cameraCrop(sg.t0 + sg.dur * k / 100, tl)).cx; peak = Math.max(peak, dir * (c - target)); }
            const end = ctr(cameraCrop(sg.t0 + sg.dur - 1e-6, tl)).cx; return { overshootPx: +peak.toFixed(1), moveLen: +Math.abs(target - start).toFixed(0), landsOn: Math.abs(end - target) < 0.5 }; }""")
        print('S3 Overshoot goes past the shot by', r['overshootPx'], 'px of a', r['moveLen'], 'px move, then lands exactly:', r['landsOn'])
        # S4 Whip smears even with blur off; other moves don't
        r = await m.evaluate("""() => { $('camBlur').value = 'off'; refreshTotal(); const tl = buildTimeline(); const mv = tl.segs.filter(s => s.kind === 'move');
            const mid = sg => sg.t0 + sg.dur / 2; return mv.map(sg => [sg.style, camBlurCount(mid(sg), tl, 480, 30, false, 1)]); }""")
        print('S4 blur samples mid-move with Motion blur OFF:', r)
        await m.evaluate("() => { $('camBlur').value = 'natural'; $('camPath').value = 'natural'; refreshTotal(); }")
        # S5 older project names map onto styles
        r = await m.evaluate("""() => { const p = { app: 'dolly', version: 1, source: { kind: 'image', w: src.w, h: src.h }, defaults: { kind: 'move', dur: 3, hold: 0.5, ease: 'inout' },
            shots: [{ full: true, out: { ease: 'out' } }, { cx: .3, cy: .4, wf: .25 }, { cx: .7, cy: .6, wf: .2 }] }; applyProject(p, { quiet: true });
            return [$('ease').value, shots[0].out.ease]; }""")
        print('S5 older project: default inout ->', r[0], '| a move out ->', r[1])
        # S6 Smooth starts and ends without a bump
        r = await m.evaluate("""() => { $('ease').value = 'smooth'; for (const s of shots) delete s.out; refreshTotal(); const tl = buildTimeline(), sg = tl.segs.find(s => s.kind === 'move');
            const x = f => ctr(cameraCrop(sg.t0 + sg.dur * f, tl)).cx; return { firstPct: +(Math.abs(x(0.01) - x(0)) / Math.abs(x(1 - 1e-6) - x(0)) * 100).toFixed(5) }; }""")
        print('S6 Smooth: distance covered in the first 1% of the time:', r['firstPct'], '% of the move')
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
