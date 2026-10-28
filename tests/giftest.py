from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio
from playwright.async_api import async_playwright
EXE = CHROMIUM

# Build GIF bytes in-page with Dolly's own encoder pieces (lzw / writeGifHeader / writeGifFrame).
BUILDERS = r"""
window.T = {};
T.bytes = (arr) => Uint8Array.from(arr);
// generic GIF writer: frames = [{x,y,w,h,idx,delay,disposal,transparent,interlace,lct}]
T.gif = (W, H, gct, frames) => {
  const out = [];
  for (const c of "GIF89a") out.push(c.charCodeAt(0));
  out.push(W & 255, W >> 8, H & 255, H >> 8, 0xF7, 0, 0);
  for (const [r,g,b] of gct) out.push(r,g,b);
  out.push(0x21,0xFF,0x0B); for (const c of "NETSCAPE2.0") out.push(c.charCodeAt(0)); out.push(3,1,0,0,0);
  for (const f of frames){
    const pk = ((f.disposal||0) << 2) | (f.transparent >= 0 ? 1 : 0);
    out.push(0x21,0xF9,4, pk, f.delay & 255, f.delay >> 8, f.transparent >= 0 ? f.transparent : 0, 0);
    let flags = 0; if (f.interlace) flags |= 0x40; if (f.lct) flags |= 0x80 | 7;
    out.push(0x2C, f.x&255, f.x>>8, f.y&255, f.y>>8, f.w&255, f.w>>8, f.h&255, f.h>>8, flags);
    if (f.lct) for (const [r,g,b] of f.lct) out.push(r,g,b);
    let idx = f.idx;
    if (f.interlace){                                    // store rows in interlaced order
      const rows = interlaceRows(f.h), s = new Uint8Array(idx.length);
      rows.forEach((y, r) => s.set(idx.subarray(y*f.w, (y+1)*f.w), r*f.w));
      idx = s;
    }
    lzw(idx, out);
  }
  out.push(0x3B);
  return Uint8Array.from(out);
};
T.pal = n => Array.from({length:256}, (_, k) => [(k*37+11)%256, (k*91+23)%256, (k*53+7)%256]);
T.solid = (w,h,k) => new Uint8Array(w*h).fill(k);
// reference decode with Chromium's ImageDecoder → composited RGBA per frame
T.reference = async (bytes) => {
  const dec = new ImageDecoder({ data: bytes, type: "image/gif" });
  await dec.tracks.ready; const n = dec.tracks.selectedTrack.frameCount;
  const outs = [];
  for (let i = 0; i < n; i++){
    const { image } = await dec.decode({ frameIndex: i });
    const c = new OffscreenCanvas(image.displayWidth, image.displayHeight), g = c.getContext("2d");
    g.drawImage(image, 0, 0); image.close();
    outs.push(g.getImageData(0,0,c.width,c.height).data);
  }
  return outs;
};
T.compare = async (bytes) => {
  const ref = await T.reference(bytes);
  const ours = await decodeGif(bytes);
  if (ref.length !== ours.frames.length) return "frame count " + ref.length + " vs " + ours.frames.length;
  let bad = 0, first = null;
  ours.frames.forEach((f, i) => {
    const d = f.canvas.getContext("2d").getImageData(0,0,ours.width,ours.height).data, r = ref[i];
    for (let p = 0; p < d.length; p += 4){
      const ok = (d[p+3] === 0 && r[p+3] === 0) ||
                 (d[p+3] === r[p+3] && d[p] === r[p] && d[p+1] === r[p+1] && d[p+2] === r[p+2]);
      if (!ok){ bad++; if (!first) first = {frame:i, px:p/4, ours:[...d.slice(p,p+4)], ref:[...r.slice(p,p+4)]}; }
    }
  });
  return bad ? {bad, first} : "identical (" + ref.length + " frames)";
};
true;
"""

async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=EXE)
        page = await b.new_page(viewport={'width':1100,'height':950})
        page.on('pageerror', lambda e: errs.append(str(e)))
        await page.goto(URL)
        await page.evaluate(BUILDERS)

        # --- A1: tricky handcrafted GIF: interlace, partial rects, transparency, disposal 1/2/3, local table
        r = await page.evaluate("""async () => {
          const W = 40, H = 30, P = T.pal();
          const frames = [
            { x:0,y:0,w:W,h:H, idx:T.solid(W,H,5), delay:10, disposal:1, transparent:-1 },
            { x:5,y:4,w:12,h:10, idx:(() => { const a = T.solid(12,10,9); for (let i=0;i<a.length;i+=3) a[i]=200; return a; })(),
              delay:10, disposal:1, transparent:200 },                                   // holes show frame 1
            { x:20,y:10,w:15,h:15, idx:T.solid(15,15,17), delay:10, disposal:2, transparent:-1 }, // cleared after
            { x:0,y:0,w:8,h:8, idx:T.solid(8,8,33), delay:10, disposal:3, transparent:-1 },      // reverted after
            { x:2,y:2,w:30,h:21, idx:(() => { const a = new Uint8Array(30*21); for (let i=0;i<a.length;i++) a[i]=(i*7)%64; return a; })(),
              delay:10, disposal:0, transparent:-1, interlace:true },
            { x:10,y:10,w:10,h:10, idx:(() => { const a = new Uint8Array(100); for (let i=0;i<100;i++) a[i]=i%4; return a; })(),
              delay:10, disposal:0, transparent:-1,
              lct: Array.from({length:256}, (_, k) => [k, 255-k, (k*3)%256]) },          // local color table
          ];
          return await T.compare(T.gif(W, H, P, frames));
        }""")
        print('A1 handcrafted (interlace/transparency/disposal 1-2-3/local table):', r)

        # --- A2: Dolly-encoded noisy GIF, forces LZW table resets
        r = await page.evaluate("""async () => {
          const W = 320, H = 180, cv = document.createElement('canvas'); cv.width = W; cv.height = H;
          const g = cv.getContext('2d'), frames = [], samples = [];
          const imgs = [];
          for (let f = 0; f < 6; f++){
            const gr = g.createLinearGradient(0,0,W,H); gr.addColorStop(0, `hsl(${f*50},70%,40%)`); gr.addColorStop(1, `hsl(${f*50+120},80%,60%)`);
            g.fillStyle = gr; g.fillRect(0,0,W,H);
            for (let i=0;i<4000;i++){ g.fillStyle = `rgb(${Math.random()*255|0},${Math.random()*255|0},${Math.random()*255|0})`; g.fillRect(Math.random()*W|0, Math.random()*H|0, 2, 2); }
            const d = g.getImageData(0,0,W,H).data; imgs.push(d);
            for (let p = 0; p < d.length; p += 64) samples.push([d[p],d[p+1],d[p+2]]);
          }
          const pal = medianCut(samples, 256), near = makeNearest(pal);
          const out = []; writeGifHeader(out, W, H, pal);
          for (const d of imgs) writeGifFrame(out, W, H, fsDither(d, W, H, pal, near), 8);
          out.push(0x3B);
          return await T.compare(Uint8Array.from(out));
        }""")
        print('A2 Dolly-encoded noisy 320x180x6 (LZW resets):', r)

        # --- B: time mapping. 10 frames x 0.1s = 1.0s; each frame a distinct solid color.
        await page.evaluate("""async () => {
          const W = 160, H = 90, P = T.pal();
          const frames = Array.from({length:10}, (_, k) => ({ x:0,y:0,w:W,h:H, idx:T.solid(W,H,k*20+3), delay:10, disposal:1, transparent:-1 }));
          window.TEST_PAL = P;
          await loadFile(new File([T.gif(W,H,P,frames)], 'clock.gif', {type:'image/gif'}));
        }""")
        st = await page.evaluate("() => ({ kind: src.kind, frames: src.frames.length, dur: src.duration, shots: shots.length, total: lastTotal, speed: curTL.speed, tc: document.getElementById('tc').textContent, mediaShown: !document.getElementById('tlMedia').hidden })")
        print('B0 GIF loaded, single FULL shot:', st)

        # helper: which source frame does output time t show? (2 FULL shots → crops identical to source)
        await page.evaluate("""() => {
          addFull(); media.speed = 'auto'; refreshTotal(); // second FULL shot; tests below start from Fit clip
          window.frameShownAt = (t) => {
            const tl = buildTimeline(), c = document.createElement('canvas'); c.width = 160; c.height = 90;
            const g = c.getContext('2d'); renderAtTime(g, 160, 90, t, tl);
            const d = g.getImageData(80, 45, 1, 1).data;
            for (let k = 0; k < 10; k++){ const [r,gg,b] = TEST_PAL[k*20+3]; if (Math.abs(d[0]-r)+Math.abs(d[1]-gg)+Math.abs(d[2]-b) < 6) return k; }
            return -1;
          };
          window.expectFrame = (t) => { const tl = buildTimeline(); return Math.min(9, Math.floor(sourceTime(t, tl) / 0.1 + 1e-9)); };
        }""")
        async def check(label, times):
            res = await page.evaluate("(ts) => ts.map(t => [t, frameShownAt(t), expectFrame(t)])", times)
            ok = all(a == e for _, a, e in res)
            info = await page.evaluate("() => ({ total: buildTimeline().total, speed: +buildTimeline().speed.toFixed(4) })")
            print(f"{label}: {'PASS' if ok else 'FAIL'} total={info['total']} speed={info['speed']} shown={[a for _,a,_ in res]}")
            if not ok: print('   detail', res)
        T = [0, 0.3, 0.9, 1.7, 2.0, 2.6, 3.2, 3.9]
        await check('B1 Auto (clip spans 4.0s sequence, 0.25x)', T)
        await page.evaluate("() => { media.speed = 2; media.end = 'loop'; refreshTotal(); }")
        await check('B2 Manual 2x, loop', T)
        await page.evaluate("() => { media.end = 'hold'; refreshTotal(); }")
        await check('B3 Manual 2x, hold last frame', T)
        await page.evaluate("() => { media.speed = 0.1; refreshTotal(); }")
        await check('B4 Manual 1/10x (camera ends mid-clip)', T)
        # hand-check of the math against the spec: Auto → s = (1.0/4.0) * t
        await page.evaluate("() => { media.speed = 'auto'; refreshTotal(); }")
        exp = [min(9, int((t*0.25)/0.1 + 1e-9)) for t in T]
        got = await page.evaluate("(ts) => ts.map(t => frameShownAt(t))", T)
        print('B5 Auto vs hand-computed spec:', 'PASS' if exp == got else f'FAIL {exp} vs {got}')

        # --- C: UI: media inspector, slider snapping to detents, transport text, viewfinder moment
        await page.locator('#tlMedia').click()
        insp = await page.evaluate("() => document.querySelector('#inspector .insp-head span').textContent")
        snaps = await page.evaluate("""() => { const r = document.querySelector('#inspector input[type=range]'); const out = [];
           for (const v of [0.61, 0.98, -0.99, 1.4, -0.31]){ r.value = v; r.dispatchEvent(new Event('input')); out.push([v, media.speed]); }
           r.dispatchEvent(new Event('change')); return out; }""")
        print('C1 media inspector:', insp)
        print('C2 log slider → speed (detents snap):', snaps)
        tc = await page.evaluate("() => document.getElementById('tc').textContent")
        print('C3 transport:', tc)
        # viewfinder shows the shot's moment: select second FULL shot (moment = middle of its 0.5s dwell at 3.5..4.0)
        await page.evaluate("() => { media.speed = 'auto'; refreshTotal(); selectShot(1); }")
        vfk = await page.evaluate("""() => { const d = vctx.getImageData(5, 5, 1, 1).data;
           for (let k = 0; k < 10; k++){ const [r,g,b] = TEST_PAL[k*20+3]; if (Math.abs(d[0]-r)+Math.abs(d[1]-g)+Math.abs(d[2]-b) < 6) return k; } return -1; }""")
        print('C4 viewfinder on shot 2 shows source frame:', vfk, '(expect', await page.evaluate("() => Math.min(9, Math.floor(sourceTime(shotMoment(1), curTL)/0.1))"), ')')

        # --- D: export a GIF from the animated source, decode it, check frames follow the mapping
        await page.evaluate("() => { selectMedia(); media.speed = 'auto'; document.getElementById('outW').value = '0'; document.getElementById('fps').value = 10; document.getElementById('dither').checked = false; refreshTotal(); }")
        await page.locator('#btnExport').click(); await page.evaluate("() => $('btnGif').click()")
        await page.wait_for_function("() => document.querySelector('#media img')", timeout=60000)
        r = await page.evaluate("""async () => {
          const blob = await (await fetch(document.querySelector('#dl a').href)).blob();
          const g = await decodeGif(new Uint8Array(await blob.arrayBuffer()));
          const tl = buildTimeline(), out = [];
          let mism = 0;
          g.frames.forEach((f, n) => {
            const d = f.canvas.getContext('2d').getImageData(Math.floor(g.width/2), Math.floor(g.height/2), 1, 1).data;
            let k = -1; for (let j = 0; j < 10; j++){ const [r,gg,b] = TEST_PAL[j*20+3]; if (Math.abs(d[0]-r)+Math.abs(d[1]-gg)+Math.abs(d[2]-b) < 12) { k = j; break; } }
            const want = Math.min(9, Math.floor(sourceTime(n / 10, tl) / 0.1 + 1e-9));
            if (k !== want) mism++; out.push(k);
          });
          return { frames: g.frames.length, mism, seq: out.join('') };
        }""")
        print('D1 exported GIF frames follow mapping:', r)
        await page.locator('#btnExport').click(); await page.evaluate("() => $('btnVideo').click()")
        await page.wait_for_function("() => document.querySelector('#media video')", timeout=60000)
        print('D2 video from GIF:', await page.evaluate("() => document.getElementById('monTitle').textContent"))

        # screenshot with a realistic layout: a few shots + media selected, manual speed with loop seams
        await page.evaluate("""() => { shots.splice(1, 0, fitRect(50, 30, 60, 0), fitRect(110, 55, 50, 0.2));
           media.speed = 0.5; media.end = 'loop'; selectMedia(); }""")
        await page.screenshot(path=OUT + '/gif_ui.png', full_page=False)
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
