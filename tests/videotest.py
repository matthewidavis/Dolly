from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio
from playwright.async_api import async_playwright
EXE = CHROMIUM

SETUP = r"""
window.VCOL = Array.from({length:20}, (_, k) => {           // 20 well-separated colors
  const hue = (k * 137) % 360, l = k % 2 ? 35 : 62;
  const c = document.createElement('canvas').getContext('2d'); c.fillStyle = `hsl(${hue},85%,${l}%)`; c.fillRect(0,0,1,1);
  return [...c.getImageData(0,0,1,1).data.slice(0,3)];
});
window.which = (d) => { let best = -1, bd = 1e9;
  VCOL.forEach((c, k) => { const e = Math.abs(d[0]-c[0]) + Math.abs(d[1]-c[1]) + Math.abs(d[2]-c[2]); if (e < bd){ bd = e; best = k; } });
  return bd < 60 ? best : -1; };
window.makeClip = async () => {                           // 20 frames @10fps = 2.0s VP8 WebM, via Dolly's own muxer
  const W = 320, H = 180, cv = document.createElement('canvas'); cv.width = W; cv.height = H;
  const g = cv.getContext('2d'), chunks = [];
  const enc = new VideoEncoder({ output: c => { const d = new Uint8Array(c.byteLength); c.copyTo(d);
      chunks.push({ key: c.type === 'key', ms: Math.round(c.timestamp/1000), data: d }); }, error: e => { throw e; } });
  enc.configure({ codec:'vp8', width:W, height:H, bitrate: 2_000_000, framerate: 10 });
  for (let k = 0; k < 20; k++){
    const [r,gg,b] = VCOL[k]; g.fillStyle = `rgb(${r},${gg},${b})`; g.fillRect(0,0,W,H);
    const f = new VideoFrame(cv, { timestamp: k * 100000, duration: 100000 }); enc.encode(f, { keyFrame: k % 5 === 0 }); f.close();
  }
  await enc.flush();
  return muxWebM(chunks, W, H, 'V_VP8', 2000);
};
window.shownAt = async (t) => {                            // exact render of output time t → which source frame
  const tl = buildTimeline(); await prepareFrame(t, tl);
  const c = document.createElement('canvas'); c.width = 64; c.height = 36; const g = c.getContext('2d');
  renderAtTime(g, 64, 36, t, tl); return which(g.getImageData(32, 18, 1, 1).data);
};
window.expectAt = (t) => { const s = sourceTime(t, buildTimeline()); const f = s / 0.1;
  return { k: Math.min(19, Math.floor(f + 1e-9)), edge: Math.abs(f - Math.round(f)) < 0.15 }; };
true;
"""

async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=EXE)
        page = await b.new_page(viewport={'width':1100,'height':950})
        page.on('pageerror', lambda e: errs.append(str(e)))
        await page.goto(URL)
        await page.evaluate(SETUP)
        await page.evaluate("async () => { const blob = await makeClip(); await loadFile(new File([blob], 'clip.webm', {type:'video/webm'})); }")
        st = await page.evaluate("() => ({ kind: src.kind, w: src.w, h: src.h, dur: +src.duration.toFixed(3), end: media.end, trim: [media.trimIn, +media.trimOut.toFixed(3)], tc: document.getElementById('tc').textContent, src: document.getElementById('roSrc').textContent })")
        print('V0 video loaded:', st)

        await page.evaluate("() => { addFull(); media.speed = 'auto'; media.end = 'hold'; refreshTotal(); }")     # two FULL shots; start from Fit clip
        async def check(label, times):
            res = await page.evaluate("""async (ts) => { const out = []; for (const t of ts){ const e = expectAt(t); out.push([t, await shownAt(t), e.k, e.edge]); } return out; }""", times)
            judged = [(t, a, e) for t, a, e, edge in res if not edge]
            ok = all(a == e for _, a, e in judged)
            tl = await page.evaluate("() => { const tl = buildTimeline(); return [tl.total, +tl.speed.toFixed(4)]; }")
            print(f"{label}: {'PASS' if ok else 'FAIL'} total={tl[0]} speed={tl[1]} shown={[a for _,a,_ in judged]} (checked {len(judged)}/{len(res)})")
            if not ok: print('   detail', res)
        T = [0.05, 0.35, 0.9, 1.45, 1.9, 2.3, 2.75, 3.3, 3.95]
        await check('V1 Auto (2.0s clip over 4.0s sequence)', T)
        T2 = [0.07, 0.31, 0.88, 1.12, 1.63, 2.21, 2.79, 3.37, 3.94]
        await page.evaluate("() => { media.speed = 2; media.end = 'loop'; refreshTotal(); }")
        await check('V2 Manual 2x loop', T2)
        await page.evaluate("() => { media.end = 'hold'; refreshTotal(); }")
        held = await page.evaluate("async (ts) => { const o = []; for (const t of ts) o.push(await shownAt(t)); return o; }", [1.12, 1.63, 2.21, 2.79, 3.37, 3.94])
        print('V3 Manual 2x hold: held frames', held, 'PASS' if all(k == 19 for k in held) else 'FAIL')
        await page.evaluate("() => { media.speed = 'auto'; media.trimIn = 0.5; media.trimOut = 1.5; refreshTotal(); }")
        await check('V4 Auto with trim 0.5–1.5s', T)
        await page.evaluate("() => { media.speed = 1; media.end = 'loop'; refreshTotal(); }")
        await check('V5 Manual 1x loop within trim', T)
        await page.evaluate("() => { media.speed = 'auto'; media.trimIn = 0; media.trimOut = src.duration; media.end = 'hold'; refreshTotal(); }")

        # async refresh: viewfinder + thumbnails converge on the right frames after the worker catches up
        await page.evaluate("() => selectShot(1)")
        await page.wait_for_timeout(900)
        r = await page.evaluate("""() => { const e = Math.min(19, Math.floor(sourceTime(shotMoment(1), curTL) / 0.1));
            const vfk = which(vctx.getImageData(4, 4, 1, 1).data);
            const th = thumbCanvases.map(c => which(c.getContext('2d').getImageData(c.width/2|0, c.height/2|0, 1, 1).data));
            const thExp = shots.map((_, i) => Math.min(19, Math.floor(sourceTime(shotMoment(i), curTL) / 0.1)));
            return { viewfinder: vfk, expect: e, thumbs: th, thumbsExpect: thExp }; }""")
        print('V6 async viewfinder/thumbs converge:', r, 'PASS' if r['viewfinder'] == r['expect'] and r['thumbs'] == r['thumbsExpect'] else 'FAIL')
        mt = await page.evaluate("""() => { const c = document.getElementById('tlMedia'), g = c.getContext('2d'); const seen = new Set();
            for (let x = 10; x < c.width; x += 12){ const k = which(g.getImageData(x, c.height/2|0, 1, 1).data); if (k >= 0) seen.add(k); }
            return { shown: !c.hidden, distinctFrames: seen.size }; }""")
        print('V7 filmstrip filled from cache:', mt)

        # trim UI: dragging In jumps the viewfinder to that source frame
        await page.evaluate("() => selectMedia()")
        await page.evaluate("() => { const r = document.querySelectorAll('#inspector .trim input')[0]; r.value = 1.23; r.dispatchEvent(new Event('input')); }")
        await page.wait_for_timeout(700)
        r = await page.evaluate("() => ({ trimView, inV: media.trimIn, vf: which(vctx.getImageData(4,4,1,1).data), head: document.querySelector('#inspector .insp-head span').textContent, label: document.querySelector('#inspector .field .val') && [...document.querySelectorAll('#inspector .field .val')].map(e => e.textContent) })")
        print('V8 trim drag shows frame at handle:', r, '(expect frame 12)')
        await page.evaluate("() => { const r = document.querySelectorAll('#inspector .trim input')[0]; r.dispatchEvent(new Event('change')); }")
        print('   after release trimView:', await page.evaluate("() => trimView"))
        await page.screenshot(path=OUT + '/video_ui.png')

        # live preview
        await page.evaluate("() => { media.trimIn = 0; media.trimOut = src.duration; media.speed = 'auto'; refreshTotal(); }")
        await page.locator('#btnPreview').click()
        await page.wait_for_timeout(1200)
        r = await page.evaluate("""() => { const v = src.video; return { live: src.live, playing: !v.paused, rate: v.playbackRate, ct: +v.currentTime.toFixed(2),
            vf: which(vctx.getImageData(4,4,1,1).data) }; }""")
        print('V9 live preview:', r)
        await page.locator('#btnPreview').click()
        print('   stopped:', await page.evaluate("() => ({ live: src.live, paused: src.video.paused, raf: previewRAF })"))
        # extreme speed → seek-driven preview path
        await page.evaluate("() => { media.speed = 100; media.end = 'loop'; refreshTotal(); }")
        await page.locator('#btnPreview').click(); await page.wait_for_timeout(600)
        print('V10 100x preview (seek-driven):', await page.evaluate("() => ({ live: src.live, canPlay: liveState && liveState.canPlay, paused: src.video.paused })"))
        await page.locator('#btnPreview').click()

        # exports from video
        await page.evaluate("() => { media.speed = 'auto'; media.trimIn = 0.4; media.trimOut = 1.6; refreshTotal(); document.getElementById('outW').value = '0'; document.getElementById('fps').value = 10; document.getElementById('dither').checked = false; }")
        await page.locator('#btnExport').click()
        note = await page.evaluate("() => !document.getElementById('exportNote').hidden")
        await page.evaluate("() => $('btnGif').click()")
        await page.wait_for_function("() => document.querySelector('#media img')", timeout=90000)
        r = await page.evaluate("""async () => {
          const blob = await (await fetch(document.querySelector('#dl a').href)).blob();
          const g = await decodeGif(new Uint8Array(await blob.arrayBuffer())); const tl = buildTimeline();
          let checked = 0, mism = 0; const seq = [];
          g.frames.forEach((f, n) => { const k = which(f.canvas.getContext('2d').getImageData(g.width/2|0, g.height/2|0, 1, 1).data);
            const s = sourceTime(n / 10, tl) / 0.1, want = Math.min(19, Math.floor(s + 1e-9)); seq.push(k);
            if (Math.abs(s - Math.round(s)) >= 0.15){ checked++; if (k !== want) mism++; } });
          return { frames: g.frames.length, checked, mism, seq: seq.join(',') };
        }""")
        print('V11 GIF export from trimmed video:', r, '| silent-note shown:', note)
        await page.locator('#btnExport').click(); await page.evaluate("() => $('btnVideo').click()")
        await page.wait_for_function("() => document.querySelector('#media video')", timeout=90000)
        r = await page.evaluate("""async () => { const v = document.querySelector('#media video');
            await new Promise(r => { if (v.readyState >= 1) r(); else v.onloadedmetadata = r; setTimeout(r, 4000); });
            return { title: document.getElementById('monTitle').textContent, dur: +v.duration.toFixed(2), w: v.videoWidth }; }""")
        print('V12 WebM export from video:', r)

        # mobile screenshot with video + media inspector
        m = await b.new_page(viewport={'width':390,'height':844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        m.on('pageerror', lambda e: errs.append('mobile: ' + str(e)))
        await m.goto(URL); await m.evaluate(SETUP)
        await m.evaluate("async () => { await loadFile(new File([await makeClip()], 'clip.webm', {type:'video/webm'})); shots.push(fitRect(100, 60, 140, 0.15)); addFull(); selectMedia(); }")
        await m.wait_for_timeout(1200)
        await m.screenshot(path=OUT + '/video_mobile.png', full_page=True)
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
