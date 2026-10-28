from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio
from playwright.async_api import async_playwright
VSETUP = open('videotest.py').read().split('SETUP = r"""')[1].split('"""')[0]
IMG = open('projtest.py').read().split('IMG = r"""')[1].split('"""')[0]
DECODE = """async (id) => { const j = jobs.find(x => x.id === id); const g = await decodeGif(new Uint8Array(await j.blob.arrayBuffer()));
  return g.frames.map(f => which(f.canvas.getContext('2d').getImageData(g.width/2|0, g.height/2|0, 1, 1).data)); }"""
async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROMIUM)
        page = await b.new_page(viewport={'width':1100,'height':950}); page.on('pageerror', lambda e: errs.append(str(e)))
        await page.goto(URL); await page.evaluate(VSETUP); await page.evaluate(IMG)
        await page.evaluate("async () => { await loadFile(new File([await makeClip()], 'clip.webm', {type:'video/webm'})); addFull(); media.speed = 'fit'; $('fps').value = 10; $('outW').value = '0'; $('dither').checked = false; refreshTotal(); }")

        # --- Q1 snapshot: queue a GIF, then change everything while it renders
        await page.evaluate("() => enqueueExport('gif')")
        await page.wait_for_function("() => jobs[0].state === 'running' && jobs[0].progress > 0.05", timeout=20000)
        await page.evaluate("() => { media.speed = 2; shots.splice(1); refreshTotal(); }")                   # edits mid-export
        await page.evaluate("async () => { await loadFile(await makeImage(800, 450, 'other.png')); }")    # even new media
        await page.wait_for_function("() => jobs[0].state === 'done'", timeout=60000)
        seq = await page.evaluate(DECODE, 1)
        print('Q1 snapshot kept through edits + new media:', ''.join(f'{k:x}' if k < 16 else 'g' for k in seq) if all(k >= 0 for k in seq) else seq,
              'PASS' if seq == list(range(20)) else 'FAIL (expect frames 0..19 from the Fit camera snapshot)')

        # --- Q2 three jobs: strictly one at a time, in order
        await page.evaluate("async () => { await loadFile(new File([await makeClip()], 'clip.webm', {type:'video/webm'})); addFull(); media.speed = 'fit'; $('fps').value = 10; refreshTotal(); }")
        await page.evaluate("""() => { window.MAXRUN = 0; window.ORDER = [];
            window.__mon = setInterval(() => { const r = jobs.filter(j => j.state === 'running'); MAXRUN = Math.max(MAXRUN, r.length);
              for (const j of r) if (!ORDER.includes(j.id)) ORDER.push(j.id); }, 20);
            $('vidFmt').value = 'webm'; enqueueExport('webm'); enqueueExport('gif'); enqueueExport('webm'); }""")
        await page.wait_for_function("() => jobs.slice(1).every(j => j.state === 'done' || j.state === 'failed')", timeout=90000)
        r = await page.evaluate("() => ({ maxRunning: MAXRUN, order: ORDER, states: jobs.map(j => j.state), kinds: jobs.map(j => j.ext) })")
        print('Q2 queue:', r, 'PASS' if r['maxRunning'] == 1 and r['order'] == [2, 3, 4] else 'FAIL')

        # --- Q3 cancel: one waiting, one running
        await page.evaluate("() => { enqueueExport('gif'); enqueueExport('gif'); }")
        await page.wait_for_function("() => jobs[4].state === 'running' && jobs[4].progress > 0.1", timeout=20000)
        await page.evaluate("() => { cancelJob(jobs[5]); cancelJob(jobs[4]); }")
        await page.wait_for_function("() => !jobRunning", timeout=20000)
        print('Q3 cancel:', await page.evaluate("() => [jobs[4].state, jobs[5].state, jobs[4].blob === undefined]"))

        # --- Q4 preview while a video job renders; the export stays frame-exact (its own player)
        await page.evaluate("() => { media.speed = 'fit'; refreshTotal(); enqueueExport('gif'); }")
        await page.wait_for_function("() => jobs[6].state === 'running'", timeout=20000)
        await page.locator('#btnPreview').click()
        await page.wait_for_timeout(800)
        live = await page.evaluate("() => ({ live: src.live, playing: !src.video.paused })")
        await page.wait_for_function("() => jobs[6].state === 'done'", timeout=60000)
        await page.locator('#btnPreview').click()
        seq = await page.evaluate(DECODE, 7)
        print('Q4 preview during export:', live, '| export exact:', seq == list(range(20)))

        # --- Q5 UI: badge, sheet rows, saved state, leave-warning logic
        st = await page.evaluate("""() => { openJobs(); const rows = [...document.querySelectorAll('#jobList .job')].map(r => [r.querySelector('.job-name').textContent, r.querySelector('.job-state').textContent, [...r.querySelectorAll('.actions button')].map(b => b.textContent).join('/')]);
            return { badge: document.getElementById('jobsCount').textContent, hidden: document.getElementById('btnJobs').hidden, rows: rows.slice(0, 3),
                     warnBefore: jobs.some(j => j.state === 'done' && !j.downloaded) }; }""")
        print('Q5 Exports sheet:', st)
        await page.evaluate("() => { for (const j of jobs) if (j.state === 'done') j.downloaded = true; renderJobs(); }")
        print('   after saving everything: badge', repr(await page.evaluate("() => document.getElementById('jobsCount').textContent")), '| would warn on leave:',
              await page.evaluate("() => jobs.some(j => j.state === 'queued' || j.state === 'running' || (j.state === 'done' && !j.downloaded))"))
        await page.screenshot(path=OUT + '/q_sheet_desktop.png')
        await page.keyboard.press('Escape')

        # --- Q6 responsiveness while a longer job runs: animation-frame gaps on the editing page
        await page.evaluate("async () => { await loadFile(await makeImage(1600, 900, 'big.png')); shots.push(fitRect(500, 300, 400, 0), fitRect(1200, 600, 300, 0.2)); refreshTotal(); $('outW').value = '1280'; $('fps').value = 30; }")
        gaps = await page.evaluate("""async () => { const g = []; let last = performance.now(), on = true;
            const loop = t => { g.push(t - last); last = t; if (on) requestAnimationFrame(loop); }; requestAnimationFrame(loop);
            const t0 = performance.now(); enqueueExport('webm');
            await new Promise(r => { const c = setInterval(() => { if (!jobRunning) { clearInterval(c); r(); } }, 50); });
            on = false; g.sort((a, b) => a - b);
            return { secs: +((performance.now() - t0) / 1000).toFixed(1), median: +g[g.length >> 1].toFixed(1), p95: +g[Math.floor(g.length * .95)].toFixed(1), max: +g[g.length - 1].toFixed(1) }; }""")
        print('Q6 page smoothness during a 1280px export (frame gaps, ms):', gaps)
        await b.close()

        # phone look: badge in the bar + Exports sheet
        b = await p.chromium.launch(executable_path=CHROMIUM)
        m = await b.new_page(viewport={'width':390,'height':844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        await m.goto(URL); await m.evaluate(IMG)
        await m.evaluate("async () => { await loadFile(await makeImage(1600, 900, 'farm.png')); shots.push(fitRect(500, 300, 400, 0)); refreshTotal(); $('outW').value = '480'; $('fps').value = 12; enqueueExport('gif'); $('vidFmt').value = 'webm'; enqueueExport('webm'); }")
        await m.wait_for_function("() => jobs[0].state === 'done' && jobs[1].state === 'running' && jobs[1].progress > .3", timeout=60000)
        await m.screenshot(path=OUT + '/q_bar.png')
        await m.evaluate("() => openJobs()"); await m.wait_for_timeout(300)
        await m.screenshot(path=OUT + '/q_sheet_phone.png')
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
