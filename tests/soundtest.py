from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio, sys
from playwright.async_api import async_playwright
CHROMIUM = CHROMIUM
CHROME = CHROME_H264
VSETUP = open('videotest.py').read().split('SETUP = r"""')[1].split('"""')[0]
IMG = open('projtest.py').read().split('IMG = r"""')[1].split('"""')[0]
AUD = r"""
window.makeWav = (secs, freq, amp = .5) => {                   // 16-bit stereo WAV tone
  const sr = 48000, n = Math.round(secs * sr), b = new DataView(new ArrayBuffer(44 + n * 4));
  const w = (o, s) => [...s].forEach((c, i) => b.setUint8(o + i, c.charCodeAt(0)));
  w(0,'RIFF'); b.setUint32(4, 36 + n*4, true); w(8,'WAVE'); w(12,'fmt '); b.setUint32(16,16,true); b.setUint16(20,1,true); b.setUint16(22,2,true);
  b.setUint32(24,sr,true); b.setUint32(28,sr*4,true); b.setUint16(32,4,true); b.setUint16(34,16,true); w(36,'data'); b.setUint32(40,n*4,true);
  for (let i = 0; i < n; i++){ const v = Math.round(Math.sin(2*Math.PI*freq*i/sr) * amp * 32767); b.setInt16(44+i*4, v, true); b.setInt16(46+i*4, v, true); }
  return new File([b.buffer], 'tone' + freq + '.wav', { type: 'audio/wav' });
};
window.makeClipWithSound = async () => {                       // 2.0s: color per 0.1s frame; 440 Hz on even frames, silent on odd
  const blob = await makeClip(), bytes = new Uint8Array(await blob.arrayBuffer());
  // re-encode: we need the video chunks, so build again with audio alongside
  const W = 320, H = 180, cv = document.createElement('canvas'); cv.width = W; cv.height = H; const g = cv.getContext('2d'), vch = [];
  const enc = new VideoEncoder({ output: c => { const d = new Uint8Array(c.byteLength); c.copyTo(d); vch.push({ key: c.type === 'key', ms: Math.round(c.timestamp/1000), us: c.timestamp, data: d }); }, error: e => { throw e; } });
  enc.configure({ codec:'vp8', width:W, height:H, bitrate: 2_000_000, framerate: 10 });
  for (let k = 0; k < 20; k++){ const [r,gg,b] = VCOL[k]; g.fillStyle = `rgb(${r},${gg},${b})`; g.fillRect(0,0,W,H);
    const f = new VideoFrame(cv, { timestamp: k * 100000, duration: 100000 }); enc.encode(f, { keyFrame: k % 5 === 0 }); f.close(); }
  await enc.flush();
  const sr = 48000, n = 2 * sr, ab = new AudioBuffer({ length: n, numberOfChannels: 2, sampleRate: sr }), ch = new Float32Array(n);
  for (let i = 0; i < n; i++){ const t = i / sr; ch[i] = (Math.floor(t * 10 + 1e-9) % 2 === 0) ? Math.sin(2*Math.PI*440*t) * .5 : 0; }
  ab.copyToChannel(ch, 0); ab.copyToChannel(ch, 1);
  const a = await encodeSound(ab, 'webm');
  return new File([muxWebM(vch, W, H, 'V_VP8', 2000, a)], 'clip-sound.webm', { type: 'video/webm' });
};
window.goertzel = (x, sr, f, from, len) => { const k = 2 * Math.cos(2 * Math.PI * f / sr); let s1 = 0, s2 = 0;
  for (let i = from; i < from + len && i < x.length; i++){ const s0 = x[i] + k * s1 - s2; s2 = s1; s1 = s0; } return Math.sqrt(s1*s1 + s2*s2 - k*s1*s2) / (len / 2); };
window.exportedAudio = async () => { const buf = await (await (await fetch(document.querySelector('#dl a').href)).blob()).arrayBuffer();
  const ab = await new OfflineAudioContext(2, 1, 48000).decodeAudioData(buf); return { x: ab.getChannelData(0), sr: ab.sampleRate, dur: ab.duration }; };
/* where 440 Hz bursts turn on, in seconds, by scanning 2 ms windows */
window.onsets = (x, sr, f) => { const win = Math.round(sr * .004), hop = Math.round(sr * .001), out = []; let on = false;
  for (let i = 0; i + win < x.length; i += hop){ const e = goertzel(x, sr, f, i, win); if (!on && e > .15){ out.push((i + win / 2) / sr); on = true; } else if (on && e < .05) on = false; } return out; };
true;
"""
async def render(page, which):
    await page.locator('#btnExport').click(); await page.wait_for_timeout(200)
    await page.evaluate("() => $('" + ('btnVideo' if which == 'video' else 'btnGif') + "').click()")
    await page.wait_for_function("() => document.querySelector('#media " + ('video' if which == 'video' else 'img') + "') && !busy", timeout=120000)
    await page.wait_for_timeout(50)

async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROMIUM, args=["--autoplay-policy=no-user-gesture-required"])
        page = await b.new_page(viewport={'width':1100,'height':950}); page.on('pageerror', lambda e: errs.append(str(e)))
        await page.goto(URL); await page.evaluate(VSETUP); await page.evaluate(IMG); await page.evaluate(AUD)

        # ---- music added before any media, then an image
        await page.evaluate("async () => loadFile(makeWav(3, 880))"); await page.wait_for_timeout(100)
        st = await page.evaluate("() => document.getElementById('status').textContent")
        await page.evaluate("async () => { await loadFile(await makeImage(800, 450, 'a.png')); shots.push(fitRect(300, 200, 240, 0)); refreshTotal(); $('vidFmt').value = 'webm'; $('fps').value = 10; $('outW').value = '480'; }")
        r = await page.evaluate("() => ({ total: lastTotal, row: !document.getElementById('tlSound').hidden, track: sound.trackName })")
        print('S1 music before media:', st, '|', r)

        # ---- music: loop + fade-out in an exported WebM (sequence 4.0s, track 3.0s)
        await render(page, 'video')
        r = await page.evaluate("""async () => { const { x, sr, dur } = await exportedAudio(); const e = t => +goertzel(x, sr, 880, Math.round(t * sr), 2400).toFixed(3);
            return { dur: +dur.toFixed(2), at: [0.5, 2.5, 3.2, 3.6, 3.95].map(t => [t, e(t)]), status: document.getElementById('status').textContent }; }""")
        print('S2 WebM with music (3s tone, 4s sequence, loop on, 1.5s fade-out):', r)
        await page.evaluate("() => { sound.trackLoop = false; refreshTotal(); }")
        await render(page, 'video')
        r = await page.evaluate("async () => { const { x, sr } = await exportedAudio(); return [2.5, 3.3, 3.8].map(t => [t, +goertzel(x, sr, 880, Math.round(t*sr), 2400).toFixed(3)]); }")
        print('   loop off → silence after the song ends at 3.0s:', r)

        # ---- video with its own sound: Natural 1× loop over a 4s sequence, music removed
        await page.evaluate("async () => { sound.track = null; sound.trackName = ''; await loadFile(await makeClipWithSound()); }")
        await page.wait_for_function("() => src && src.audio", timeout=10000)
        await page.evaluate("() => { addFull(); refreshTotal(); }")
        info = await page.evaluate("() => ({ audio: +src.audio.duration.toFixed(2), speed: curTL.speed, soundRow: !document.getElementById('tlSound').hidden })")
        await render(page, 'video')
        r = await page.evaluate("""async () => { const { x, sr } = await exportedAudio(), tl = buildTimeline(); let bad = 0, n = 0; const seq = [];
            for (let f = 0; f < 40; f++){ const t = (f + .5) / 10, on = goertzel(x, sr, 440, Math.round((t - .03) * sr), Math.round(.06 * sr)) > .1;
              const s = sourceTime(t, tl), want = Math.floor(s * 10 + 1e-9) % 2 === 0; seq.push(on ? 1 : 0); n++; if (on !== want) bad++; }
            const ons = onsets(x, sr, 440).slice(0, 12), exp = ons.map(o => Math.round(o * 5) / 5);
            const err = ons.map((o, i) => Math.round((o - exp[i]) * 10000) / 10);
            return { checked: n, wrong: bad, pattern: seq.join(''), onsetErrorMs: err }; }""")
        print('S3 video sound follows the picture through loops (WebM):', info, r)

        await page.evaluate("() => { media.speed = 2; refreshTotal(); }")
        await render(page, 'video')
        r = await page.evaluate("async () => { try { const { x, sr } = await exportedAudio(); let m = 0; for (let t = .1; t < 3.9; t += .1) m = Math.max(m, goertzel(x, sr, 440, Math.round(t*sr), 2400)); return { maxAt2x: +m.toFixed(4) }; } catch (e) { return { audioTrack: 'none (silent export, as intended)', soundOf: soundOf(curTL) }; } }")
        print('S4 at 2× the video sound is muted:', r)
        await page.evaluate("() => { media.speed = 1; refreshTotal(); }")

        # ---- UI: inspector, undo, preview sound
        await page.locator('#tlSound').click()
        insp = await page.evaluate("() => ({ head: document.querySelector('#inspector .insp-head span').textContent, fields: [...document.querySelectorAll('#inspector .field > label')].map(l => l.firstChild.textContent.trim()), buttons: [...document.querySelectorAll('#inspector .actions button')].map(b => b.textContent) })")
        print('S5 sound inspector (video sound, no music):', insp)
        await page.evaluate("async () => { await addTrack(makeWav(5, 880)); }")
        d0 = await page.evaluate("undoStack.length")
        await page.evaluate("() => { selectSound(); const r = [...document.querySelectorAll('#inspector input[type=range]')][1]; for (const v of [.6,.4,.2]){ r.value = v; r.dispatchEvent(new Event('input')); } r.dispatchEvent(new Event('change')); }")
        await page.wait_for_timeout(30)
        insp2 = await page.evaluate("() => ({ fields: [...document.querySelectorAll('#inspector .field > label')].map(l => l.firstChild.textContent.trim()), musicVol: sound.trackVol, steps: undoStack.length })")
        await page.keyboard.press('Control+z'); await page.wait_for_timeout(30)
        print('   with music:', insp2, '| one slider drag = one undo step:', insp2['steps'] - d0 == 1, '| undo restores volume:', await page.evaluate("sound.trackVol"))
        if await page.evaluate("() => !soundOn"): await page.locator('#btnMute').click()
        await page.locator('#btnPreview').click(); await page.wait_for_timeout(400)
        pv = await page.evaluate("() => ({ playing: !!previewSound, ctx: audioCtx && audioCtx.state, sources: previewSound ? previewSound.sources.length : 0 })")
        await page.locator('#btnPreview').click(); await page.wait_for_timeout(50)
        print('S6 preview plays the mix:', pv, '| stopped:', await page.evaluate("previewSound === null"))
        await page.screenshot(path=OUT + '/sound_ui.png')

        # ---- project keeps sound settings; music must be re-added
        r = await page.evaluate("async () => { sound.fadeOut = 3.3; const p = await buildProject(false); sound.track = null; sound.fadeOut = 1; applyProject(p); return [sound.fadeOut, document.getElementById('status').textContent]; }")
        print('S7 project restores sound settings:', r)
        await b.close()

        # ---- MP4 with sound in Chrome (no AAC encoder on Linux → Opus in MP4), plus sync
        b = await p.chromium.launch(executable_path=CHROME, args=["--autoplay-policy=no-user-gesture-required"])
        page = await b.new_page(viewport={'width':1100,'height':950}); page.on('pageerror', lambda e: errs.append('chrome: ' + str(e)))
        await page.goto(URL); await page.evaluate(VSETUP); await page.evaluate(AUD)
        await page.evaluate("async () => { await loadFile(await makeClipWithSound()); }")
        await page.wait_for_function("() => src && src.audio", timeout=10000)
        await page.evaluate("() => { addFull(); refreshTotal(); $('fps').value = 10; $('outW').value = '0'; }")
        await render(page, 'video')
        r = await page.evaluate("""async () => { const { x, sr, dur } = await exportedAudio(), tl = buildTimeline(); let bad = 0; const seq = [];
            for (let f = 0; f < 40; f++){ const t = (f + .5) / 10, on = goertzel(x, sr, 440, Math.round((t - .03) * sr), Math.round(.06 * sr)) > .1;
              const want = Math.floor(sourceTime(t, tl) * 10 + 1e-9) % 2 === 0; seq.push(on ? 1 : 0); if (on !== want) bad++; }
            const ons = onsets(x, sr, 440).slice(0, 12), err = ons.map(o => Math.round((o - Math.round(o * 5) / 5) * 10000) / 10);
            const v = document.querySelector('#media video'); await new Promise(r => { if (v.readyState >= 1) r(); else v.onloadedmetadata = r; setTimeout(r, 3000); });
            return { title: document.getElementById('monTitle').textContent, status: document.getElementById('status').textContent.slice(0, 60),
                     audioDur: +dur.toFixed(2), playerDur: +v.duration.toFixed(2), wrong: bad, pattern: seq.join(''), onsetErrorMs: err }; }""")
        print('S8 MP4 with sound (Chrome):', r)
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
