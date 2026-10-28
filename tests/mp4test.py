from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio
from playwright.async_api import async_playwright
CHROME = CHROME_H264
CHROMIUM = CHROMIUM
SETUP = open('videotest.py').read().split('SETUP = r"""')[1].split('"""')[0]
IMG = open('projtest.py').read().split('IMG = r"""')[1].split('"""')[0]
MP4 = r"""
window.be32 = (u, p) => ((u[p] << 24) | (u[p+1] << 16) | (u[p+2] << 8) | u[p+3]) >>> 0;
window.boxes = (u, s, e) => { const o = []; let p = s; while (p + 8 <= e){ const sz = be32(u, p); o.push({ type: String.fromCharCode(...u.subarray(p+4, p+8)), s: p, size: sz }); if (sz < 8) break; p += sz; } return o; };
window.child = (u, b, type, skip = 0) => boxes(u, b.s + 8 + skip, b.s + b.size).find(x => x.type === type);
window.inspectMp4 = (u) => {
  const top = boxes(u, 0, u.length);
  const moov = top.find(b => b.type === 'moov');
  const stbl = ['trak','mdia','minf','stbl'].reduce((b, t) => child(u, b, t), moov);
  const mdhd = child(u, child(u, child(u, moov, 'trak'), 'mdia'), 'mdhd');
  const stsd = child(u, stbl, 'stsd'), avc1 = boxes(u, stsd.s + 16, stsd.s + stsd.size)[0];
  const avcC = boxes(u, avc1.s + 8 + 78, avc1.s + avc1.size).find(b => b.type === 'avcC');
  const stsz = child(u, stbl, 'stsz'), stco = child(u, stbl, 'stco'), stss = child(u, stbl, 'stss'), stts = child(u, stbl, 'stts');
  const n = be32(u, stsz.s + 16), sizes = [], offs = [], keys = new Set();
  for (let i = 0; i < n; i++){ sizes.push(be32(u, stsz.s + 20 + 4*i)); offs.push(be32(u, stco.s + 16 + 4*i)); }
  for (let i = 0, k = be32(u, stss.s + 12); i < k; i++) keys.add(be32(u, stss.s + 16 + 4*i) - 1);
  const mdat = top.find(b => b.type === 'mdat');
  let inBounds = true, nalOk = true;
  sizes.forEach((sz, i) => { if (offs[i] < mdat.s + 8 || offs[i] + sz > mdat.s + mdat.size) inBounds = false;
    let p = offs[i]; const end = offs[i] + sz; while (p < end){ const L = be32(u, p); if (L === 0 || p + 4 + L > end){ nalOk = false; break; } p += 4 + L; } });
  const desc = u.slice(avcC.s + 8, avcC.s + avcC.size);
  const codec = 'avc1.' + [...desc.subarray(1, 4)].map(x => x.toString(16).padStart(2, '0')).join('');
  return { order: top.map(b => b.type).join(','), n, sizes, offs, keys, desc, codec, inBounds, nalOk,
           timescale: be32(u, mdhd.s + 20), duration: be32(u, mdhd.s + 24), sttsDelta: be32(u, stts.s + 20), hasCtts: !!child(u, stbl, 'ctts') };
};
window.lastOutputBytes = async () => new Uint8Array(await (await (await fetch(document.querySelector('#dl a').href)).blob()).arrayBuffer());
true;
"""
async def render_video(page):
    await page.locator('#btnExport').click(); await page.wait_for_timeout(150)
    await page.evaluate("() => $('btnVideo').click()")
    await page.wait_for_function("() => document.querySelector('#media video') && !busy", timeout=90000)

async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME)
        page = await b.new_page(viewport={'width':1100,'height':950})
        page.on('pageerror', lambda e: errs.append(str(e)))
        await page.goto(URL); await page.evaluate(SETUP); await page.evaluate(IMG); await page.evaluate(MP4)
        # MP4 needs an H.264 encoder. Playwright's own Chromium has none (Dolly then exports WebM,
        # which other suites cover), so without Google Chrome these checks are skipped, not failed.
        h264 = await page.evaluate("""async () => { try { return !!(window.VideoEncoder && (await VideoEncoder.isConfigSupported({ codec: 'avc1.42001f', width: 640, height: 360, bitrate: 2e6, framerate: 30 })).supported); } catch (_) { return false; } }""")
        if not h264:
            print("SKIPPED: this browser has no H.264 encoder, so the MP4 checks can't run here.")
            print("         Set DOLLY_CHROME to a Google Chrome executable to run them (see README).")
            print("ERRORS: none")
            await b.close()
            return

        # ---- M1–M3: still image sequence → MP4
        await page.evaluate("""async () => { await loadFile(await makeImage(1600, 900, 'wide.png'));
            shots.push(fitRect(500, 300, 400, 0), fitRect(1200, 600, 300, 0.3)); addFull(); setOut(0, 'kind', 'fade'); refreshTotal();
            $('outW').value = '480'; $('fps').value = 24; }""")
        await render_video(page)
        r = await page.evaluate("""async () => { const v = document.querySelector('#media video');
            await new Promise(r => { if (v.readyState >= 1) r(); else v.onloadedmetadata = r; setTimeout(r, 4000); });
            return { title: document.getElementById('monTitle').textContent, link: document.querySelector('#dl a').textContent,
                     playerDuration: +v.duration.toFixed(3), w: v.videoWidth, h: v.videoHeight, expect: +buildTimeline().total.toFixed(3),
                     fmtSelected: $('vidFmt').value }; }""")
        print('M1 plays in a real <video>:', r)
        st = await page.evaluate("""async () => { const i = inspectMp4(await lastOutputBytes());
            return { order: i.order, samples: i.n, keyframes: i.keys.size, codec: i.codec, offsetsInMdat: i.inBounds, nalLengthsValid: i.nalOk,
                     timescale: i.timescale, mediaDuration: i.duration, ticksPerFrame: i.sttsDelta, ctts: i.hasCtts }; }""")
        print('M2 structure:', st)
        r = await page.evaluate("""async () => {
          const u = await lastOutputBytes(), i = inspectMp4(u), fps = 24, tl = buildTimeline();
          const W = 480, H = 270, ref = document.createElement('canvas'); ref.width = W; ref.height = H; const rc = ref.getContext('2d');
          const out = document.createElement('canvas'); out.width = W; out.height = H; const oc = out.getContext('2d');
          const frames = [];
          const dec = new VideoDecoder({ output: f => { oc.drawImage(f, 0, 0); frames.push(oc.getImageData(0,0,W,H).data); f.close(); }, error: e => { throw e; } });
          dec.configure({ codec: i.codec, description: i.desc });
          for (let k = 0; k < i.n; k++) dec.decode(new EncodedVideoChunk({ type: i.keys.has(k) ? 'key' : 'delta', timestamp: Math.round(k * 1e6 / fps), data: u.subarray(i.offs[k], i.offs[k] + i.sizes[k]) }));
          await dec.flush();
          let worst = 0, sum = 0;
          for (let k = 0; k < frames.length; k++){ renderAtTime(rc, W, H, k / fps, tl); const a = rc.getImageData(0,0,W,H).data, d = frames[k];
            let e = 0; for (let p = 0; p < a.length; p += 4) e += Math.abs(a[p]-d[p]) + Math.abs(a[p+1]-d[p+1]) + Math.abs(a[p+2]-d[p+2]);
            e /= (a.length / 4) * 3; worst = Math.max(worst, e); sum += e; }
          return { decoded: frames.length, of: i.n, meanErrPerChannel: +(sum / frames.length).toFixed(2), worstFrame: +worst.toFixed(2) }; }""")
        print('M3 every sample decodes; matches reference renders:', r)

        # ---- M4: timing in a real player: color-coded video, Real time mode, seek MP4 frame by frame
        await page.evaluate("""async () => { await loadFile(new File([await makeClip()], 'clip.webm', {type:'video/webm'}));
            addFull(); media.speed = 'fit'; refreshTotal(); $('outW').value = '0'; $('fps').value = 10; }""")
        await render_video(page)
        r = await page.evaluate("""async () => {
          const v = document.createElement('video'); v.muted = true; v.src = document.querySelector('#dl a').href;
          await new Promise(r => v.onloadeddata = r);
          const c = document.createElement('canvas'); c.width = 32; c.height = 18; const g = c.getContext('2d'); const seen = [];
          for (let n = 0; n < 20; n++){ v.currentTime = (n + 0.5) / 10; await new Promise(r => v.onseeked = r);
            g.drawImage(v, 0, 0, 32, 18); seen.push(which(g.getImageData(16, 9, 1, 1).data)); }
          return { duration: +v.duration.toFixed(3), seen }; }""")
        print('M4 seeking the MP4 shows source frame n at n:', r, 'PASS' if r['seen'] == list(range(20)) else 'FAIL')

        # ---- M5: exact durations at awkward frame rates
        durs = []
        for fps in [8, 12, 25, 30, 60]:
            await page.evaluate(f"() => {{ $('fps').value = {fps}; $('outW').value = '0'; }}")
            await render_video(page)
            d = await page.evaluate("""async () => { const i = inspectMp4(await lastOutputBytes()); const v = document.querySelector('#media video');
                await new Promise(r => { if (v.readyState >= 1) r(); else v.onloadedmetadata = r; setTimeout(r, 4000); });
                return [+(i.duration / i.timescale).toFixed(4), +v.duration.toFixed(4), i.n]; }""")
            durs.append((fps, d))
        print('M5 duration (container, player, frames) per fps — sequence is 2.0s:', durs)

        # ---- M6: B-frame safety net: synthetic reordered timestamps → ctts + edit list, offsets non-negative
        r = await page.evaluate("""async () => {
          const desc = inspectMp4(await lastOutputBytes()).desc, d = new Uint8Array([0,0,0,1,0x65]);
          const order = [0, 3, 1, 2, 6, 4, 5];   // I P B B P B B (presentation index in decode order)
          const chunks = order.map((k, i) => ({ key: i === 0, us: k * 1e5, data: d }));
          const u = new Uint8Array(await muxMP4(chunks, 64, 36, 10, desc).arrayBuffer());
          const top = boxes(u, 0, u.length), moov = top.find(b => b.type === 'moov'), trak = child(u, moov, 'trak');
          const stbl = ['mdia','minf','stbl'].reduce((b, t) => child(u, b, t), trak), ctts = child(u, stbl, 'ctts');
          const edts = child(u, trak, 'edts'), elst = child(u, edts, 'elst');
          const offs = []; for (let i = 0; i < order.length; i++) offs.push(be32(u, ctts.s + 16 + 8*i + 4));
          const dts = order.map((_, i) => i * 1000), present = offs.map((o, i) => dts[i] + o - be32(u, elst.s + 20));
          return { cttsOffsets: offs, editShift: be32(u, elst.s + 20), presentationTicks: present, expected: order.map(k => k * 1000) }; }""")
        print('M6 reordered frames:', r, 'PASS' if r['presentationTicks'] == r['expected'] else 'FAIL')

        # project remembers the format
        r = await page.evaluate("async () => { $('vidFmt').value = 'webm'; const p = await buildProject(false); $('vidFmt').value = 'mp4'; applyProject(p); return [p.export.vidFmt, $('vidFmt').value]; }")
        print('M7 project keeps video format:', r)
        await b.close()

        # ---- M8: browser without H.264 → MP4 disabled, WebM made, message
        b2 = await p.chromium.launch(executable_path=CHROMIUM)
        pg = await b2.new_page(); pg.on('pageerror', lambda e: errs.append('chromium: ' + str(e)))
        await pg.goto(URL); await pg.evaluate(IMG); await pg.evaluate(MP4)
        await pg.evaluate("async () => { await loadFile(await makeImage(800, 450, 'w.png')); shots.push(fitRect(300, 200, 200, 0)); refreshTotal(); $('fps').value = 10; $('outW').value = '480'; }")
        await pg.locator('#btnExport').click(); await pg.wait_for_timeout(400)
        sheet = await pg.evaluate("() => ({ selected: $('vidFmt').value, mp4Option: $('vidFmt').options[0].textContent, disabled: $('vidFmt').options[0].disabled, note: $('vidFmtNote').textContent })")
        print('M8 no-H.264 browser, export sheet:', sheet)
        await pg.evaluate("() => { $('vidFmt').options[0].disabled = false; $('vidFmt').value = 'mp4'; }")   # force MP4 anyway
        await pg.evaluate("() => $('btnVideo').click()")
        await pg.wait_for_function("() => document.querySelector('#media video') && !busy", timeout=60000)
        print('   forced MP4 →', await pg.evaluate("() => [document.getElementById('monTitle').textContent, document.getElementById('status').textContent]"))
        await pg.locator('#btnExport').click(); await pg.wait_for_timeout(200)
        await pg.screenshot(path=OUT + '/export_sheet.png')
        await b2.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
