from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio
from playwright.async_api import async_playwright
VSETUP = open('videotest.py').read().split('SETUP = r"""')[1].split('"""')[0]
IMG = open('projtest.py').read().split('IMG = r"""')[1].split('"""')[0]
BUILD = open('giftest.py').read().split('BUILDERS = r"""')[1].split('"""')[0]
AUD = open('soundtest.py').read().split('AUD = r"""')[1].split('"""')[0]
async def detached(page, js):
    n = await page.evaluate("() => window.__d || 0")
    await page.evaluate("() => { setTimeout(async () => { try { " + js + " } catch (e) { window.__err = String(e); } window.__d = (window.__d || 0) + 1; }, 0); }")
    await page.wait_for_function(f"() => (window.__d || 0) > {n}", timeout=30000)
SNAP = """() => ({ cur: currentProject.name, projects: projects.map(p => p.name + (p === currentProject ? '*' : '') + (p.restoreData ? (p.restoreData.video ? '[needs video]' : '[saved]') : '')),
  src: src && src.name, shots: shots.map(s => [Math.round(s.x), Math.round(s.y), Math.round(s.w), +(s.rot || 0).toFixed(3), s.dwell ?? null, s.pin ?? null, s.out ? s.out.kind : null]),
  dur: $('dur').value, outW: $('outW').value, speed: media.speed, undo: undoStack.length, status: document.getElementById('status').textContent })"""
async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROMIUM)
        ctx = await b.new_context(viewport={'width':1100,'height':950})
        page = await ctx.new_page(); page.on('pageerror', lambda e: errs.append(str(e)))
        async def setup():
            await page.evaluate(VSETUP); await page.evaluate(IMG); await page.evaluate(BUILD); await page.evaluate(AUD)
        await page.goto(URL); await setup()
        print('R0 first visit (nothing saved):', await page.evaluate("() => [projects.length, currentProject.name, getComputedStyle(document.getElementById('drop')).display !== 'none']"))

        # project 1: image with custom shots, pin-free, settings, music
        await detached(page, "await loadFile(await makeImage(1600, 900, 'farm.png')); shots.push(fitRect(500, 300, 400, 0.15), fitRect(1200, 600, 300, 0)); shots[1].dwell = 1.7; setOut(0, 'kind', 'fade'); $('dur').value = 4.2; $('outW').value = '960'; await addTrack(makeWav(3, 880)); sound.trackVol = 0.5; refreshTotal(); renameProject(currentProject, 'Farm hero');")
        # project 2: a GIF
        await detached(page, """newProject(false); const W=160,H=90,P=T.pal(); const fr = Array.from({length:10}, (_, k) => ({x:0,y:0,w:W,h:H, idx:T.solid(W,H,k*20+3), delay:10, disposal:1, transparent:-1}));
            await loadFile(new File([T.gif(W,H,P,fr)], 'clock.gif', {type:'image/gif'})); shots.push(fitRect(60, 40, 60, 0)); media.speed = 2; refreshTotal();""")
        # project 3: a video with a pin
        await detached(page, "newProject(false); await loadFile(new File([await makeClip()], 'clip.webm', {type:'video/webm'})); shots.push(fitRect(100, 60, 140, 0)); addFull(); shots[2].pin = 1.3; refreshTotal();")
        await page.evaluate("() => switchProject(projects[0])")
        before = await page.evaluate(SNAP)
        await page.wait_for_timeout(1800)                                   # autosave runs ~1 s after the last change
        stored = await page.evaluate("async () => { const s = await idb.get('kv', 'session'); const k = await idb.keys('blobs'); return { n: s.projects.length, names: s.projects.map(e => e.name), current: s.projects.findIndex(e => e.current), blobs: k.length, video: s.projects[2].video, thumbs: s.projects.map(e => !!e.thumb) }; }")
        print('R1 saved:', stored)
        # edits don't re-store media
        await page.evaluate("() => { shots[1].dwell = 1.8; refreshTotal(); }"); await page.wait_for_timeout(1500)
        print('   blobs after another edit:', await page.evaluate("async () => (await idb.keys('blobs')).length"), '(still 2: images and GIFs are stored once)')
        before = await page.evaluate(SNAP)

        # ---- reload: the open project comes straight back; others are listed
        await page.reload(); await setup()
        await page.wait_for_function("() => src && src.name === 'farm.png'", timeout=15000)
        after = await page.evaluate(SNAP)
        same = after['shots'] == before['shots'] and after['dur'] == before['dur'] and after['outW'] == before['outW']
        print('R2 after reload:', after['projects'], '| current restored exactly:', same, '| undo starts fresh:', after['undo'] == 0)
        print('   toast:', repr(after['status']))
        print('   music:', await page.evaluate("() => [sound.trackName, sound.trackVol, !!sound.track]"))

        # ---- the GIF project restores when opened
        await page.evaluate("() => switchProject(projects[1])")
        await page.wait_for_function("() => src && src.kind === 'gif'", timeout=15000)
        g = await page.evaluate(SNAP)
        print('R3 GIF project on switch:', g['src'], g['shots'], 'speed', g['speed'], '| frames:', await page.evaluate("() => src.frames.length"))

        # ---- the video project asks for its file by name and length
        await page.evaluate("() => switchProject(projects[2])")
        prompt = await page.evaluate("() => [document.getElementById('btnOpenBig').textContent, document.querySelector('.drop-sub').firstChild.textContent.trim()]")
        print('R4 video prompt:', prompt)
        await detached(page, "await loadFile(new File([await makeClip()], 'clip.webm', {type:'video/webm'}));")
        v = await page.evaluate(SNAP)
        print('   same file → applied silently:', v['shots'][2][5] == 1.3 and len(v['shots']) == 3, '| status:', repr(v['status']))
        # a different-length video: still applies, and says so
        await page.evaluate("() => { currentProject.restoreData = { data: projectData(captureProject()), video: { name: 'clip.webm', duration: 1.42 } }; }")
        await detached(page, "await loadFile(new File([await makeClip()], 'other.webm', {type:'video/webm'}));")
        print('   different length → applied with a note:', repr(await page.evaluate("() => document.getElementById('status').textContent")))

        # ---- reload again, then Start fresh clears everything for next time
        await page.wait_for_timeout(1500)
        await page.reload(); await setup()
        await page.wait_for_function("() => projects.length === 3", timeout=15000)
        print('R5 second reload keeps the list:', await page.evaluate("() => projects.map(p => p.name + (p === currentProject ? '*' : ''))"), '| toast:', repr(await page.evaluate("() => document.getElementById('status').textContent")))
        await page.evaluate("() => startFresh()"); await page.wait_for_timeout(600)
        await page.reload(); await setup(); await page.wait_for_timeout(800)
        print('R6 after Start fresh + reload:', await page.evaluate("() => [projects.length, currentProject.name, !!src, getComputedStyle(document.getElementById('drop')).display !== 'none']"),
              '| blobs left:', await page.evaluate("async () => (await idb.keys('blobs')).length"))

        # ---- Start fresh from the toast link
        await detached(page, "await loadFile(await makeImage(800, 450, 'x.png')); shots.push(fitRect(300, 200, 200, 0)); refreshTotal();")
        await page.wait_for_timeout(1500)
        await page.reload(); await setup()
        await page.wait_for_function("() => src && src.name === 'x.png'", timeout=15000)
        await page.locator('#status .undo-link').click(); await page.wait_for_timeout(300)
        print('R7 toast "Start fresh":', await page.evaluate("() => [projects.length, currentProject.name, !!src]"))
        await b.close()

        # phone look after a reload: toast + project sheet with unopened projects (thumbnails from storage)
        b = await p.chromium.launch(executable_path=CHROMIUM)
        ctx = await b.new_context(viewport={'width':390,'height':844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        m = await ctx.new_page(); await m.goto(URL); await m.evaluate(VSETUP); await m.evaluate(IMG)
        n0 = 0
        await m.evaluate("() => { setTimeout(async () => { await loadFile(await makeImage(1600, 900, 'farm.png')); shots.push(fitRect(500,300,400,0)); refreshTotal(); newProject(false); await loadFile(await makeImage(900, 1200, 'portrait.png')); shots.push(fitRect(450,500,400,0)); refreshTotal(); newProject(false); await loadFile(new File([await makeClip()], 'interview.webm', {type:'video/webm'})); refreshTotal(); switchProject(projects[0]); window.__go = 1; }, 0); }")
        await m.wait_for_function("() => window.__go", timeout=30000); await m.wait_for_timeout(1800)
        await m.reload(); await m.wait_for_function("() => src && src.name === 'farm.png'", timeout=15000); await m.wait_for_timeout(200)
        await m.screenshot(path=OUT + '/rec_toast.png')
        await m.locator('#btnProjects').click(); await m.wait_for_timeout(300)
        await m.screenshot(path=OUT + '/rec_sheet.png')
        await m.keyboard.press('Escape')
        await m.evaluate("() => switchProject(projects[2])"); await m.wait_for_timeout(300)
        await m.screenshot(path=OUT + '/rec_video.png')
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
