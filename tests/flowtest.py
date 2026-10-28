from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio
from playwright.async_api import async_playwright
IMG = open('auditshots.py').read().split('IMG = r"""')[1].split('"""')[0]
VSETUP = open('videotest.py').read().split('SETUP = r"""')[1].split('"""')[0]
PIX = """(tl, t) => { const c = document.createElement('canvas'); c.width = 160; c.height = 100; const g = c.getContext('2d'); renderAtTime(g, 160, 100, t, tl, 30);
  const d = g.getImageData(0, 0, 160, 100).data; let r = 0, gg = 0, b = 0; for (let i = 0; i < d.length; i += 4){ r += d[i]; gg += d[i+1]; b += d[i+2]; } const n = d.length / 4; return [Math.round(r/n), Math.round(gg/n), Math.round(b/n)]; }"""
async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROMIUM)
        page = await b.new_page(viewport={'width':1100,'height':900}); page.on('pageerror', lambda e: errs.append(str(e)))
        await page.goto(URL); await page.evaluate(IMG); await page.evaluate(VSETUP)
        await page.evaluate("() => { setTimeout(async () => { await loadFile(await photo()); shots.splice(0); shots.push(fitRect(300, 250, 380, 0), fitRect(1200, 650, 380, 0)); $('hold').value = 1; $('dur').value = 2; refreshTotal(); window.__a = 1; }, 0); }")
        await page.wait_for_function("() => window.__a")
        await page.evaluate(f"() => {{ window.PIX = {PIX}; }}")
        # F1 each transition: starts on A, ends on B, and has its signature in the middle
        r = await page.evaluate("""() => { const out = {};
          for (const k of ['dipblack', 'dipwhite', 'swish', 'zoom']){ $('trans').value = k; refreshTotal(); const tl = buildTimeline(), sg = tl.segs.find(s => s.kind === 'fx');
            const A = PIX({ ...tl, segs: [{ kind: 'hold', a: sg.a, t0: 0, dur: 99, life: 'still' }], total: 99 }, 1),
                  B = PIX({ ...tl, segs: [{ kind: 'hold', a: sg.b, t0: 0, dur: 99, life: 'still' }], total: 99 }, 1);
            const s0 = PIX(tl, sg.t0 + 1e-4), s1 = PIX(tl, sg.t0 + sg.dur - 1e-3), mid = PIX(tl, sg.t0 + sg.dur / 2);
            const near = (x, y) => Math.max(...x.map((v, i) => Math.abs(v - y[i]))) <= 3;
            out[k] = { startsOnA: near(s0, A), endsOnB: near(s1, B), middle: mid }; }
          $('trans').value = 'move'; refreshTotal(); return out; }""")
        for k, v in r.items(): print(f'F1 {k:9s}', v)
        # F2 continuous: passes through the middle shot at its dwell midpoint, without stopping
        await page.evaluate("() => { shots.splice(0); shots.push(fitRect(250, 250, 300, 0), fitRect(800, 450, 360, 0.08), fitRect(1350, 700, 300, 0)); $('flow').value = 'continuous'; $('handheld').value = 'off'; refreshTotal(); }")
        r = await page.evaluate("""() => { const tl = buildTimeline(), hs = tl.spans.filter(s => s.type === 'shot'), mid = hs[1].t0 + hs[1].dur / 2, sh = shots[1];
          const c = cameraCrop(mid, tl), a = cameraCrop(mid - 0.05, tl), b = cameraCrop(mid + 0.05, tl);
          const speed = Math.hypot(ctr(b).cx - ctr(a).cx, ctr(b).cy - ctr(a).cy) / 0.1;
          const first0 = cameraCrop(hs[0].t0 + 0.1, tl), first1 = cameraCrop(hs[0].t0 + hs[0].dur - 1e-4, tl), last = cameraCrop(tl.total - 0.01, tl);
          let maxStep = 0, prev = null; for (let k = 0; k <= 600; k++){ const t = tl.total * k / 600, q = cameraCrop(t, tl); if (prev) maxStep = Math.max(maxStep, Math.hypot(ctr(q).cx - ctr(prev).cx, ctr(q).cy - ctr(prev).cy)); prev = q; }
          return { exactAtMiddleShot: Math.abs(ctr(c).cx - ctr(sh).cx) < 0.5 && Math.abs(c.w - sh.w) < 0.5 && Math.abs(rotOf(c) - rotOf(sh)) < 1e-6,
                   speedThroughIt: +speed.toFixed(0), firstHoldStill: first0.x === first1.x && first0.w === first1.w, endsOnLast: Math.abs(ctr(last).cx - ctr(shots[2]).cx) < 0.5,
                   maxStepPerFramePx: +maxStep.toFixed(1) }; }""")
        print('F2 continuous:', r)
        r = await page.evaluate("""() => { $('flow').value = 'stop'; refreshTotal(); const tl = buildTimeline(), hs = tl.spans.filter(s => s.type === 'shot'), mid = hs[1].t0 + hs[1].dur / 2;
          const a = cameraCrop(mid - 0.05, tl), b = cameraCrop(mid + 0.05, tl); return +(Math.hypot(ctr(b).cx - ctr(a).cx, ctr(b).cy - ctr(a).cy) / 0.1).toFixed(0); }""")
        print('   for comparison, Stop at each shot: speed at that moment =', r, 'px/s (stopped)')
        # F3 a crossfade splits the flight into two runs
        r = await page.evaluate("""() => { $('flow').value = 'continuous'; setOut(1, 'kind', 'fade'); refreshTotal(); const tl = buildTimeline();
          const runs = new Set(tl.segs.filter(s => s.cont).map(s => s.cont)); delete shots[1].out; refreshTotal(); return { runs: runs.size, fadeKept: tl.segs.some(s => s.kind === 'fade') }; }""")
        print('F3 crossfade in a continuous sequence:', r)
        # F4 settings: per-move transition chips, project round trip, undo
        await page.evaluate("() => { selectLink(0); }"); await page.wait_for_timeout(150)
        await page.locator('#inspector .trans-chips button', has_text='Whip pan').click(); await page.wait_for_timeout(100)
        k = await page.evaluate("() => [shots[0].out.kind, document.querySelectorAll('.link')[0].className]")
        pr = await page.evaluate("async () => { const p = await buildProject(false); $('flow').value = 'stop'; delete shots[0].out; applyProject(p, { quiet: true }); return [p.defaults.flow, $('flow').value, shots[0].out && shots[0].out.kind]; }")
        print('F4 move 1 set to Whip pan:', k, '| project round trip:', pr)
        await page.screenshot(path=OUT + '/flow_move.png')
        # F5 exports with every transition (no errors, right frame count)
        r = await page.evaluate("""async () => { deselect(); $('flow').value = 'stop'; shots.splice(0); for (let k = 0; k < 5; k++) shots.push(fitRect(250 + k * 280, 300 + (k % 2) * 300, 320, 0));
          ['dipblack', 'dipwhite', 'swish', 'zoom'].forEach((k, i) => setOut(i, 'kind', k)); $('dur').value = 0.8; $('outW').value = '480'; $('fps').value = 15; refreshTotal();
          enqueueExport('gif'); const job = jobs[jobs.length - 1];
          await new Promise(r => { const c = setInterval(() => { if (job.state === 'done' || job.state === 'failed'){ clearInterval(c); r(); } }, 50); });
          const g = job.state === 'done' ? await decodeGif(new Uint8Array(await job.blob.arrayBuffer())) : null;
          return [job.state, job.error || '', g ? g.frames.length : 0, Math.round(buildTimeline().total * 15)]; }""")
        print('F5 GIF export through all four new transitions:', r)
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
