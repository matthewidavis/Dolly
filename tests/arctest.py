from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio, math
from playwright.async_api import async_playwright
IMG = open('auditshots.py').read().split('IMG = r"""')[1].split('"""')[0]
async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROMIUM)
        page = await b.new_page(viewport={'width':1100,'height':900}); page.on('pageerror', lambda e: errs.append(str(e)))
        await page.goto(URL); await page.evaluate(IMG)
        await page.evaluate("() => { setTimeout(async () => { await loadFile(await photo()); shots.splice(0); shots.push(fitRect(250, 300, 300, 0), fitRect(650, 650, 300, 0), fitRect(1050, 350, 300, 0), fitRect(1400, 700, 260, 0)); $('hold').value = 1; $('dur').value = 2; $('handheld').value = 'off'; $('holdStyle').value = 'still'; refreshTotal(); window.__a = 1; }, 0); }")
        await page.wait_for_function("() => window.__a")
        HELP = """window.SPEED = (tl, t, d = 0.04) => { const a = ctr(cameraCrop(t - d, tl)), b = ctr(cameraCrop(t + d, tl)); return Math.hypot(b.cx - a.cx, b.cy - a.cy) / (2 * d); };
                  window.DIR = (tl, t, d = 0.06) => { const a = ctr(cameraCrop(t - d, tl)), b = ctr(cameraCrop(t, tl)), c = ctr(cameraCrop(t + d, tl));
                    const a1 = Math.atan2(b.cy - a.cy, b.cx - a.cx), a2 = Math.atan2(c.cy - b.cy, c.cx - b.cx); let x = Math.abs(a2 - a1) * 180 / Math.PI; return +Math.min(x, 360 - x).toFixed(1); };"""
        await page.evaluate("() => { " + HELP + " }")
        before = await page.evaluate("""() => { const tl = buildTimeline(), h = tl.spans.filter(s => s.type === 'shot');
            return { speedAtB: +SPEED(tl, h[1].t0 + h[1].dur / 2).toFixed(0), cont: tl.segs.some(s => s.cont) }; }""")
        print('before (all dwells 1 s): speed at shot 2 =', before['speedAtB'], 'px/s | flows anywhere:', before['cont'])
        # PT1 dwell 0 on shots 2 and 3 → the camera flows through them
        r = await page.evaluate("""() => { shots[1].dwell = 0; shots[2].dwell = 0; refreshTotal(); const tl = buildTimeline(), h = tl.spans.filter(s => s.type === 'shot');
            const at = k => { const c = cameraCrop(h[k].t0 + 1e-6, tl); return Math.hypot(ctr(c).cx - ctr(shots[k]).cx, ctr(c).cy - ctr(shots[k]).cy) < 0.5 && Math.abs(c.w - shots[k].w) < 0.5; };
            return { exactAt2: at(1), exactAt3: at(2), speedThrough2: +SPEED(tl, h[1].t0).toFixed(0), speedThrough3: +SPEED(tl, h[2].t0).toFixed(0),
                     turnAt2deg: DIR(tl, h[1].t0), turnAt3deg: DIR(tl, h[2].t0),
                     shot1Still: SPEED(tl, h[0].t0 + h[0].dur / 2) < 0.5, shot4Still: SPEED(tl, h[3].t0 + h[3].dur / 2) < 0.5 }; }""")
        print('PT1 dwell 0 on shots 2-3:', r)
        # PT2 the old behaviour, for comparison: Continuous off and dwell 0 used to stop dead
        # PT3 a Push-in hold on shot 1: the flight departs from the drifted framing, no jump
        r = await page.evaluate("""() => { shots[0].life = 'pushin'; refreshTotal(); const tl = buildTimeline(), h = tl.spans.filter(s => s.type === 'shot'), te = h[0].t0 + h[0].dur;
            const a = cameraCrop(te - 1e-4, tl), b = cameraCrop(te + 1e-4, tl); delete shots[0].life; refreshTotal();
            return { jumpPx: +Math.max(Math.abs(a.w - b.w), Math.hypot(ctr(a).cx - ctr(b).cx, ctr(a).cy - ctr(b).cy)).toFixed(2) }; }""")
        print('PT3 departure from a Push-in hold into the flight:', r)
        r = await page.evaluate("""() => { $('flow').value = 'continuous'; shots[0].life = 'float'; refreshTotal(); const tl = buildTimeline(), h = tl.spans.filter(s => s.type === 'shot'), te = h[0].t0 + h[0].dur;
            const a = cameraCrop(te - 1e-4, tl), b = cameraCrop(te + 1e-4, tl); delete shots[0].life; $('flow').value = 'stop'; refreshTotal();
            return { jumpPx: +Math.max(Math.abs(a.w - b.w), Math.hypot(ctr(a).cx - ctr(b).cx, ctr(a).cy - ctr(b).cy)).toFixed(2) }; }""")
        print('    same in Continuous mode with a Float hold (the latent bug):', r)
        # PT4 single moves between stopping shots keep their own style
        r = await page.evaluate("""() => { delete shots[1].dwell; delete shots[2].dwell; setOut(0, 'ease', 'overshoot'); refreshTotal(); const tl = buildTimeline();
            const mv = tl.segs.filter(s => s.kind === 'move'); const out = { anyFlow: mv.some(s => s.cont), firstStyle: mv[0].style }; delete shots[0].out; refreshTotal(); return out; }""")
        print('PT4 all shots with a dwell:', r)
        # ARC1 geometry
        r = await page.evaluate("""() => { const a = fitRect(300, 500, 300, 0), b = fitRect(1300, 500, 300, 0), out = {};
            for (const arc of [null, 'left', 'right']){ const s0 = cropBetween(a, b, 0, 'direct', arc), s1 = cropBetween(a, b, 1, 'direct', arc), m = cropBetween(a, b, 0.5, 'direct', arc);
              out[arc || 'straight'] = { endsExact: Math.abs(s0.x - a.x) < 1e-6 && Math.abs(s1.x - b.x) < 1e-6 && Math.abs(s0.y - a.y) < 1e-6 && Math.abs(s1.y - b.y) < 1e-6, midDy: +(ctr(m).cy - 500).toFixed(1) }; }
            return out; }""")
        print('ARC1 move to the right, 1000 px (left of travel = up on screen):', r)
        # draw the camera path for: stop-everywhere, pass-through, and a single arc
        await page.evaluate("""() => { window.trace = (setup) => { setup(); refreshTotal(); const tl = buildTimeline(), pts = [];
            for (let k = 0; k <= 400; k++){ const c = ctr(cameraCrop(tl.total * k / 400, tl)); pts.push([c.cx, c.cy]); } return pts; }; }""")
        paths = await page.evaluate("""() => ({
            stop: trace(() => { for (const s of shots) delete s.dwell; }),
            flow: trace(() => { shots[1].dwell = 0; shots[2].dwell = 0; }),
            arc:  trace(() => { for (const s of shots) delete s.dwell; setOut(1, 'arc', 'left'); }),
            shots: shots.map(s => [ctr(s).cx, ctr(s).cy]) })""")
        await page.evaluate("() => { delete shots[1].out; refreshTotal(); }")
        # ARC2 the Path tool on a phone, project round trip, invalid values ignored
        m = await b.new_page(viewport={'width':390,'height':844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        m.on('pageerror', lambda e: errs.append(str(e)))
        await m.goto(URL); await m.evaluate(IMG)
        await m.evaluate("() => { setTimeout(async () => { await loadFile(await photo()); shots.push(fitRect(500, 400, 360, 0), fitRect(1200, 600, 360, 0)); deselect(); document.getElementById('status').classList.remove('show'); window.__a = 1; }, 0); }")
        await m.wait_for_function("() => window.__a"); await m.wait_for_timeout(300)
        await m.locator('.link').nth(1).tap(); await m.wait_for_timeout(250)
        await m.locator('#moveArc').tap(); await m.wait_for_timeout(250)
        await m.locator('#inspector .arc-chips button', has_text='Arc right').tap(); await m.wait_for_timeout(200)
        await m.evaluate("() => document.getElementById('status').classList.remove('show')")
        await m.screenshot(path=OUT + '/arc_panel.png')
        r = await m.evaluate("""async () => { const set = shots[1].out && shots[1].out.arc; const p = await buildProject(false); delete shots[1].out; applyProject(p, { quiet: true });
            const back = shots[1].out && shots[1].out.arc; const bad = JSON.parse(JSON.stringify(p)); bad.shots[1].out = { arc: 'sideways' }; applyProject(bad, { quiet: true });
            return [set, back, shots[1].out ? shots[1].out.arc : null]; }""")
        print('ARC2 phone Path tool sets:', r[0], '| project round trip:', r[1], '| invalid "sideways" ignored:', r[2] is None)
        await b.close()
    import json; open(OUT + '/arcpaths.json', 'w').write(json.dumps(paths))
    print('ERRORS:', errs or 'none')
asyncio.run(main())
