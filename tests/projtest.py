from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio, json
from playwright.async_api import async_playwright
EXE = CHROMIUM
BUILDERS = open('giftest.py').read().split('BUILDERS = r"""')[1].split('"""')[0]
IMG = r"""
window.makeImage = async (W, H, name) => {
  const c = document.createElement('canvas'); c.width = W; c.height = H; const g = c.getContext('2d');
  const gr = g.createLinearGradient(0,0,W,H); gr.addColorStop(0,'#1d3b6e'); gr.addColorStop(1,'#e8a33d'); g.fillStyle = gr; g.fillRect(0,0,W,H);
  g.fillStyle = '#fff'; for (let i = 0; i < 30; i++) g.fillRect((i*53)%W, (i*97)%H, 14, 14);
  return new File([await new Promise(r => c.toBlob(r, 'image/png'))], name, { type: 'image/png' });
};
true;
"""
SNAP = """() => ({ shots: shots.map(s => ({ x:+s.x.toFixed(3), y:+s.y.toFixed(3), w:+s.w.toFixed(3), rot:+(s.rot||0).toFixed(4), full:!!s.full, dwell:s.dwell ?? null, out:s.out ?? null })),
  defaults: defaults(), outW: $('outW').value, fps: $('fps').value, dither: $('dither').checked, gifPal: $('gifPal').value,
  media: src.animated ? { ...media } : null, total: lastTotal })"""

async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=EXE)
        ctx = await b.new_context(accept_downloads=True, viewport={'width':1100,'height':950})
        page = await ctx.new_page(); page.on('pageerror', lambda e: errs.append(str(e)))
        await page.goto(URL); await page.evaluate(BUILDERS); await page.evaluate(IMG)

        # ---------- per-frame palettes: quality vs shared on a colorful moving source
        await page.evaluate("""async () => {
          const W = 200, H = 120, frames = [];
          for (let f = 0; f < 12; f++){              // each frame: its own family of 256 colors (hue band per frame)
            const pal = Array.from({length:256}, (_, k) => { const c = document.createElement('canvas').getContext('2d');
              c.fillStyle = `hsl(${f*30 + (k%32)},${40 + (k>>5)*7}%,${25 + (k%17)*3}%)`; c.fillRect(0,0,1,1); return [...c.getImageData(0,0,1,1).data.slice(0,3)]; });
            const idx = new Uint8Array(W*H); for (let i = 0; i < idx.length; i++) idx[i] = ((i % W) * 3 + ((i / W) | 0) * 5) & 255;
            frames.push({ x:0,y:0,w:W,h:H, idx, delay:10, disposal:1, transparent:-1, lct: pal });
          }
          await loadFile(new File([T.gif(W, H, T.pal(), frames)], 'rainbow.gif', {type:'image/gif'}));
          addFull(); media.speed = 'fit'; refreshTotal();
          document.getElementById('outW').value = '0'; document.getElementById('fps').value = 10; document.getElementById('dither').checked = false;
        }""")
        async def export_err(mode):
            await page.evaluate(f"() => document.getElementById('gifPal').value = '{mode}'")
            await page.locator('#btnExport').click(); await page.evaluate("() => $('btnGif').click()")
            await page.wait_for_function("() => document.querySelector('#media img') && !jobRunning && !jobs.some(j => j.state === 'queued')", timeout=60000)
            return await page.evaluate("""async () => {
              const bytes = new Uint8Array(await (await (await fetch(document.querySelector('#dl a').href)).blob()).arrayBuffer());
              const g = await decodeGif(bytes), tl = buildTimeline(), c = document.createElement('canvas'); c.width = g.width; c.height = g.height;
              const cx = c.getContext('2d'); let err = 0, n = 0;
              g.frames.forEach((f, i) => { renderAtTime(cx, g.width, g.height, i / 10, tl);
                const a = cx.getImageData(0,0,g.width,g.height).data, o = f.canvas.getContext('2d').getImageData(0,0,g.width,g.height).data;
                for (let p = 0; p < a.length; p += 4){ err += Math.abs(a[p]-o[p]) + Math.abs(a[p+1]-o[p+1]) + Math.abs(a[p+2]-o[p+2]); n++; } });
              const title = document.getElementById('monTitle').textContent;
              return { frames: g.frames.length, meanErr: +(err / n).toFixed(2), kb: Math.round(bytes.length/1024), title, cmp: await T.compare(bytes) };
            }""")
        shared = await export_err('shared'); perf = await export_err('frame'); auto = await export_err('auto')
        print('P1 shared palette  :', shared)
        print('P2 per-frame       :', perf)
        print('P3 auto (GIF src)  :', {k: auto[k] for k in ('meanErr','title')})
        print('   per-frame error reduced by', f"{(1 - perf['meanErr']/shared['meanErr'])*100:.0f}%")

        # ---------- projects: build a rich sequence on a 1600x900 image
        await page.evaluate("""async () => { await loadFile(await makeImage(1600, 900, 'wide.png'));
          shots.push(fitRect(500, 300, 400, 0), fitRect(1200, 600, 300, 0.3)); addFull();
          shots[1].dwell = 1.7; setOut(0, 'kind', 'fade'); setOut(1, 'dur', 4.2); setOut(1, 'ease', 'linear');
          document.getElementById('trans').value = 'cut'; document.getElementById('hold').value = 1.1;
          document.getElementById('outW').value = '960'; document.getElementById('fps').value = 24; document.getElementById('gifPal').value = 'frame';
          refreshTotal(); }""")
        before = await page.evaluate(SNAP)
        # save through the real button → real download
        await page.evaluate("() => { if (src) deselect(); }"); await page.locator('#btnMenu').click()
        async with page.expect_download() as dl:
            await page.locator('#btnSaveProj').click()
        d = await dl.value; path = await d.path(); fname = d.suggested_filename
        proj = json.load(open(path))
        print('S1 saved:', fname, '| shots', len(proj['shots']), '| embedded:', 'embedded' in proj, f"({round(len(proj['embedded']['data'])*3/4/1024)} KB image)", '| keys', sorted(proj.keys()))

        # load into a fresh page with no media: embedded image restores everything
        p2 = await ctx.new_page(); p2.on('pageerror', lambda e: errs.append('p2: ' + str(e)))
        await p2.goto(URL)
        await p2.evaluate("() => { if (src) deselect(); }"); await p2.locator('#btnMenu').click()
        async with p2.expect_file_chooser() as fc:
            await p2.locator('#btnLoadProj').click()
        await (await fc.value).set_files(path)
        await p2.wait_for_function("() => src && shots.length === 4", timeout=10000)
        after = await p2.evaluate(SNAP)
        same = before == after
        print('S2 fresh page restore (embedded):', 'IDENTICAL' if same else 'DIFF', '| status:', await p2.evaluate("() => document.getElementById('status').textContent"))
        if not same:
            for k in before:
                if before[k] != after[k]: print('   diff', k, before[k], '!=', after[k])

        # apply to a different-aspect image: relative positions, everything in bounds
        await p2.evaluate("async () => { const bytes = await (await fetch(arguments[0])).arrayBuffer(); }".replace("arguments[0]", "'data:,'"))
        await p2.evaluate(IMG)
        res = await p2.evaluate("""async () => { const p = await buildProject(false);
            await loadFile(await makeImage(900, 900, 'square.png')); applyProject(p);
            const inside = shots.every(s => cornersOf(s).every(([x,y]) => x >= -1e-6 && y >= -1e-6 && x <= src.w + 1e-6 && y <= src.h + 1e-6));
            const rel = shots.filter(s => !s.full).map(s => [+((s.x + s.w/2)/src.w).toFixed(3), +((s.y + s.h/2)/src.h).toFixed(3), +(s.w/src.w).toFixed(3), +s.rot.toFixed(3)]);
            const orig = p.shots.filter(s => !s.full).map(s => [+s.cx.toFixed(3), +s.cy.toFixed(3), +s.wf.toFixed(3), +s.rot.toFixed(3)]);
            return { inside, rel, orig, ar: +(shots[1].w / shots[1].h).toFixed(3), status: document.getElementById('status').textContent }; }""")
        print('S3 template on 900x900:', res)

        # pending flow: project without media, then open an image
        p3 = await ctx.new_page(); p3.on('pageerror', lambda e: errs.append('p3: ' + str(e)))
        await p3.goto(URL); await p3.evaluate(IMG)
        lean = dict(proj); lean.pop('embedded')
        await p3.evaluate("async (j) => loadFile(new File([JSON.stringify(j)], 'lean.dolly.json', {type:'application/json'}))", lean)
        st1 = await p3.evaluate("() => ({ src: !!src, pending: !!pendingProject, status: document.getElementById('status').textContent })")
        await p3.evaluate("async () => loadFile(await makeImage(1600, 900, 'wide.png'))")
        st2 = await p3.evaluate("() => ({ shots: shots.length, pending: !!pendingProject, status: document.getElementById('status').textContent })")
        print('S4 waiting project:', st1, '→', st2)

        # robustness: junk, wrong app, hostile values
        out = []
        for txt in ['not json', '{"app":"other","shots":[]}',
                    json.dumps({"app":"dolly","version":1,"shots":[{"cx":"x","cy":None,"wf":99,"rot":1e9,"dwell":-5,"out":{"kind":"evil","dur":"NaN","ease":"__proto__"}}, None, 7],
                                "defaults":{"dur":1e6,"hold":-1,"kind":"zzz"},"export":{"outW":"9999","fps":-3},"media":{"speed":"warp"}})]:
            out.append(await p3.evaluate("async (t) => { await loadFile(new File([t], 'x.json', {type:'application/json'})); return [document.getElementById('status').textContent, shots.length, shots.map(s => [+s.w.toFixed(1), +(s.rot||0).toFixed(3), s.dwell ?? null, s.out ?? null]), $('dur').value, $('hold').value, $('outW').value, $('fps').value]; }", txt))
        for o in out: print('S5 robustness:', o)

        # mobile toolbar with four buttons
        m = await b.new_page(viewport={'width':390,'height':844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        await m.goto(URL); await m.evaluate(IMG); await m.evaluate("async () => loadFile(await makeImage(1600, 900, 'wide.png'))")
        await m.evaluate("() => { if (src) deselect(); }"); await m.locator('#btnMenu').click(); await m.wait_for_timeout(250)
        await m.screenshot(path=OUT + '/proj_mobile.png')
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
