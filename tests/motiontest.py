from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio, math, time
from playwright.async_api import async_playwright
VSETUP = open('videotest.py').read().split('SETUP = r"""')[1].split('"""')[0]
BUILDERS = open('giftest.py').read().split('BUILDERS = r"""')[1].split('"""')[0]
PIX = """async ([t, fps]) => { const tl = buildTimeline(); await prepareFrame(t, tl, fps);
  const c = document.createElement('canvas'); c.width = 32; c.height = 18; const g = c.getContext('2d');
  renderAtTime(g, 32, 18, t, tl, fps); return [...g.getImageData(16, 9, 1, 1).data.slice(0, 3)]; }"""
def avg(cols, ws):
    return [sum(c[i] * w for c, w in zip(cols, ws)) for i in range(3)]
def close(a, b, tol=4): return max(abs(x - y) for x, y in zip(a, b)) <= tol
async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROMIUM)
        page = await b.new_page(viewport={'width':1100,'height':950}); page.on('pageerror', lambda e: errs.append(str(e)))
        await page.goto(URL); await page.evaluate(VSETUP); await page.evaluate(BUILDERS)
        t0 = time.time()
        await page.evaluate("async () => { await loadFile(new File([await makeClip()], 'clip.webm', {type:'video/webm'})); addFull(); }")
        VC = await page.evaluate("VCOL")
        print('M0 measured frame duration:', await page.evaluate("() => [src.frameDur && +src.frameDur.toFixed(4), Math.round(src.fpsHint)]"), '(clip is 10 fps)', f'| load took {time.time()-t0:.1f}s')

        # --- speed-up 4×, export 10 fps → each output frame spans 4 source frames: centred window ±0.15 s of source
        await page.evaluate("() => { media.speed = 4; media.end = 'loop'; media.motion = 'auto'; $('fps').value = 10; refreshTotal(); }")
        ok = 0; rows = []
        for t in [0.33, 0.87, 1.42, 2.06, 3.18]:
            got = await page.evaluate(PIX, [t, 10])
            s = 4 * t
            fr = [math.floor(((s + d) % 2.0) * 10 + 1e-9) % 20 for d in (-0.15, -0.05, 0.05, 0.15)]
            exp = avg([VC[k] for k in fr], [0.25] * 4)
            ok += close(got, exp); rows.append((t, fr, got, [round(x) for x in exp]))
        print(f'M1 4× Auto = motion blur of 4 frames: {ok}/5 match')
        for r in rows[:2]: print('   ', r)
        await page.evaluate("() => { media.motion = 'off'; refreshTotal(); }")
        ok = 0
        for t in [0.33, 0.87, 1.42]:
            got = await page.evaluate(PIX, [t, 10]); k = math.floor(((4 * t) % 2.0) * 10 + 1e-9) % 20
            ok += close(got, VC[k], 2)
        print(f'M2 4× Off = single frames: {ok}/3 match')

        # --- slow motion 1/4×: Auto stays steppy; Blend crossfades by position between frames
        await page.evaluate("() => { media.speed = 0.25; media.motion = 'auto'; refreshTotal(); }")
        ok = 0; rows = []
        for t in [0.6, 1.0, 2.2]:
            got = await page.evaluate(PIX, [t, 10]); k = math.floor(0.25 * t * 10 + 1e-9)
            ok += close(got, VC[k], 6); rows.append((t, 0.25 * t, k, got, VC[k], [i for i, c in enumerate(VC) if close(c, got, 2)]))
        print(f'M3 1/4× Auto = steppy single frames: {ok}/3 match')
        for r in rows: print('   ', r)
        await page.evaluate("() => { media.motion = 'blend'; refreshTotal(); }")
        ok = 0; rows = []
        for t in [0.6, 1.0, 2.2, 3.0]:
            s = 0.25 * t; k = math.floor(s * 10 + 1e-9); w = s * 10 - k
            exp = avg([VC[k], VC[k + 1]], [1 - w, w]) if w > 1e-3 else VC[k]
            got = await page.evaluate(PIX, [t, 10]); ok += close(got, exp); rows.append((t, k, round(w, 3), got, [round(x) for x in exp]))
        print(f'M4 1/4× Blend = crossfade by position: {ok}/4 match'); print('   ', rows[0]); print('   ', rows[1])

        # --- inspector: Motion shows only when it would act
        vis = []
        for spd in [1, 4, 0.25]:
            await page.evaluate(f"() => {{ media.speed = {spd}; refreshTotal(); selectMedia(); }}")
            vis.append((spd, await page.evaluate("() => { const f = [...document.querySelectorAll('#inspector .field > label')].map(l => l.firstChild.textContent.trim()); const n = document.querySelector('#inspector .field + .note'); return [f.includes('Motion'), n ? n.textContent : null]; }")))
        print('M5 Motion field shown only when relevant:', vis)

        # --- export: GIF from video at 4× (Auto) is really blended, and how long blending costs
        async def export_gif(motion):
            await page.evaluate(f"() => {{ media.speed = 4; media.motion = '{motion}'; refreshTotal(); $('outW').value = '0'; $('fps').value = 10; $('dither').checked = false; }}")
            t1 = time.time()
            await page.locator('#btnExport').click(); await page.evaluate("() => $('btnGif').click()")
            await page.wait_for_function("() => document.querySelector('#media img') && !busy", timeout=120000)
            dt = time.time() - t1
            frames = await page.evaluate("""async () => { const g = await decodeGif(new Uint8Array(await (await (await fetch(document.querySelector('#dl a').href)).blob()).arrayBuffer()));
                return g.frames.map(f => [...f.canvas.getContext('2d').getImageData(g.width/2|0, g.height/2|0, 1, 1).data.slice(0, 3)]); }""")
            return frames, dt
        fa, ta = await export_gif('auto'); fo, to = await export_gif('off')
        ok = 0
        for n, got in enumerate(fa):
            s = 4 * (n / 10)
            fr = [math.floor(((s + d) % 2.0) * 10 + 1e-9) % 20 for d in (-0.15, -0.05, 0.05, 0.15)]
            fr = [math.floor((max(0, n / 10 + d / 4) * 4 % 2.0) * 10 + 1e-9) % 20 for d in (-0.15, -0.05, 0.05, 0.15)]
            ok += close(got, avg([VC[k] for k in fr], [0.25] * 4), 6)
        print(f'M6 exported GIF at 4× Auto is motion-blurred: {ok}/{len(fa)} frames match | export {ta:.1f}s blended vs {to:.1f}s off')

        # --- GIF source: same rules use the GIF's own frame timing
        await page.evaluate("""async () => { const W=160,H=90,P=T.pal(); window.TEST_PAL = P;
            const fr = Array.from({length:10}, (_, k) => ({x:0,y:0,w:W,h:H, idx:T.solid(W,H,k*20+3), delay:10, disposal:1, transparent:-1}));
            await loadFile(new File([T.gif(W,H,P,fr)], 'c.gif', {type:'image/gif'})); addFull(); media.speed = 0.25; media.motion = 'blend'; refreshTotal(); }""")
        P = await page.evaluate("TEST_PAL")
        GC = [P[k * 20 + 3] for k in range(10)]
        got = await page.evaluate(PIX, [1.0, 10]); s = 0.25; k = 2; w = 0.5
        print('M7 GIF 1/4× Blend at s=0.25 (halfway frames 2→3):', got, 'expect', [round(x) for x in avg([GC[2], GC[3]], [0.5, 0.5])],
              'PASS' if close(got, avg([GC[2], GC[3]], [0.5, 0.5])) else 'FAIL')
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
