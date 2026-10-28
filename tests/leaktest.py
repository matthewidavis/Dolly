from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio
from playwright.async_api import async_playwright
VSETUP = open('videotest.py').read().split('SETUP = r"""')[1].split('"""')[0]
IMG = open('projtest.py').read().split('IMG = r"""')[1].split('"""')[0]
async def run(page, js):
    n = await page.evaluate("() => window.__d || 0")
    await page.evaluate("() => { setTimeout(async () => { try { " + js + " } catch (e) { window.__err = String(e); } window.__d = (window.__d || 0) + 1; }, 0); }")
    await page.wait_for_function(f"() => (window.__d || 0) > {n}", timeout=60000)
async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROMIUM)
        page = await b.new_page(viewport={'width':1100,'height':900}); page.on('pageerror', lambda e: errs.append(str(e)))
        await page.goto(URL); await page.evaluate(VSETUP); await page.evaluate(IMG)
        await page.evaluate("() => { window.REVOKED = []; const o = URL.revokeObjectURL; URL.revokeObjectURL = u => { REVOKED.push(u); return o.call(URL, u); }; }")
        clip = "new File([await makeClip()], 'clip.webm', {type:'video/webm'})"
        # K1 closing a video project releases its video
        await run(page, f"await loadFile({clip}); window.V1 = src; window.U1 = src.video.src; addFull(); refreshTotal(); newProject(false); await loadFile(await makeImage(800, 450, 'a.png'));")
        await page.evaluate("() => closeProject(projects[0])")
        print('K1 closed video project: video released', await page.evaluate("() => [V1.disposed === true, REVOKED.includes(U1)]"))
        # K2 a duplicate shares the video: closing the original keeps it
        await run(page, f"await loadFile({clip}); window.V2 = src; addFull(); refreshTotal(); duplicateProject(currentProject);")
        await page.evaluate("() => closeProject(projects.find(q => q !== currentProject && q.state && q.state.src === V2))")
        ok = await page.evaluate("async () => { await src.ensure(0.5); const c = src.frameAt(0.5, 'full'); return [!V2.disposed, src === V2, !!c && c.width > 0]; }")
        print('K2 closed the original of a duplicate: video kept and still working', ok)
        # K3 replaced by an image, the video lives on in undo; undo brings it back working
        await run(page, "await loadFile(await makeImage(640, 360, 'b.png'));")
        await page.evaluate("() => { const others = projects.filter(q => q !== currentProject); for (const q of others) closeProject(q); }")
        r = await page.evaluate("() => [V2.disposed === true, undoStack.some(h => h.src === V2)]")
        await page.evaluate("() => undo()"); await page.wait_for_timeout(100)
        ok = await page.evaluate("async () => { await src.ensure(1.0); const c = src.frameAt(1.0, 'full'); return [src === V2, !V2.disposed, !!c && c.width > 0]; }")
        print('K3 video only in undo history: disposed', r[0], '| in history', r[1], '| after undo it works:', ok)
        # K4 "let them finish": released only after the export completes
        await page.evaluate("() => { $('outW').value = '480'; $('fps').value = 10; enqueueExport('gif'); }")
        await page.wait_for_function("() => jobs.length && jobs[jobs.length - 1].state === 'running'", timeout=20000)
        await page.evaluate("() => { newProject(false); }")
        await run(page, "await loadFile(await makeImage(640, 360, 'c.png'));")
        await page.evaluate("() => { const pv = projects.find(q => q.state && q.state.src === V2); closeProject(pv); closeProject(pv, 'finish'); }")
        during = await page.evaluate("() => V2.disposed === true")
        await page.wait_for_function("() => jobs[jobs.length - 1].state === 'done'", timeout=60000); await page.wait_for_timeout(100)
        print('K4 let-finish: disposed during the export:', during, '| after it finished:', await page.evaluate("() => V2.disposed === true"), '| export ok:', await page.evaluate("() => !!jobs[jobs.length - 1].blob"))
        # K5 Start fresh releases everything
        await run(page, f"await loadFile({clip}); window.V5 = src; addFull(); refreshTotal();")
        await page.evaluate("() => startFresh()")
        print('K5 Start fresh released the video:', await page.evaluate("() => V5.disposed === true"))
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
