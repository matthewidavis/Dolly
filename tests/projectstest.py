from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio
from playwright.async_api import async_playwright
VSETUP = open('videotest.py').read().split('SETUP = r"""')[1].split('"""')[0]
IMG = open('projtest.py').read().split('IMG = r"""')[1].split('"""')[0]
DETACH = lambda js: "() => { setTimeout(async () => { " + js + " window.__done = (window.__done || 0) + 1; }, 0); }"
STATE = """() => ({ title: document.getElementById('projTitle').textContent, src: src && src.name, shots: shots.map(s => Math.round(s.w)),
  dur: $('dur').value, undo: undoStack.length, projects: projects.map(p => p.name + (p === currentProject ? '*' : '')),
  emptyShown: getComputedStyle(document.getElementById('drop')).display !== 'none', timeline: !document.getElementById('timeline').hidden })"""
async def run(page, js):
    n = await page.evaluate("() => window.__done || 0")
    await page.evaluate(DETACH(js))
    await page.wait_for_function(f"() => (window.__done || 0) > {n}", timeout=30000)
async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROMIUM)
        page = await b.new_page(viewport={'width':1100,'height':950}); page.on('pageerror', lambda e: errs.append(str(e)))
        await page.goto(URL); await page.evaluate(VSETUP); await page.evaluate(IMG)
        print('PR0 start:', await page.evaluate("() => document.getElementById('projTitle').textContent"))

        # project 1: an image with edits and undo history
        await run(page, "await loadFile(await makeImage(1600, 900, 'farm.png')); shots.push(fitRect(500, 300, 400, 0)); refreshTotal(); await Promise.resolve(); shots.push(fitRect(1200, 600, 300, 0.2)); refreshTotal(); $('dur').value = 4.5; $('dur').dispatchEvent(new Event('input'));")
        s1 = await page.evaluate(STATE); print('PR1 project 1:', s1)
        # new project: empty state, then its own media and settings
        await page.evaluate("() => newProject(false)")
        print('PR2 new project is empty:', await page.evaluate(STATE))
        await run(page, "await loadFile(await makeImage(900, 900, 'beach.png')); shots.push(fitRect(450, 450, 300, 0)); refreshTotal(); $('dur').value = 1.5; $('dur').dispatchEvent(new Event('input'));")
        s2 = await page.evaluate(STATE); print('   project 2:', s2)
        # switch back: everything of project 1 returns, including its own undo history and settings
        await page.evaluate("() => switchProject(projects[0])")
        back = await page.evaluate(STATE)
        print('PR3 back to project 1 restored:', back['src'] == 'farm.png' and back['shots'] == s1['shots'] and back['dur'] == s1['dur'] and back['undo'] == s1['undo'], back)
        await page.keyboard.press('Control+z'); await page.wait_for_timeout(50)
        u = await page.evaluate("() => shots.length")
        await page.evaluate("() => switchProject(projects[1])")
        print('   undo in project 1 only:', u, 'shots there | project 2 untouched:', await page.evaluate("() => shots.map(s => Math.round(s.w))") == s2['shots'])
        await page.evaluate("() => switchProject(projects[0])")
        await page.keyboard.press('Control+Shift+z'); await page.wait_for_timeout(50)

        # duplicate: same shots, independent from then on, fresh undo
        await page.evaluate("() => duplicateProject(currentProject)")
        d = await page.evaluate(STATE)
        await page.evaluate("() => { shots[1].dwell = 2.2; shots.pop(); refreshTotal(); }")
        await page.evaluate("() => switchProject(projects[0])")
        orig = await page.evaluate("() => [shots.length, shots[1].dwell ?? null]")
        print('PR4 duplicate:', d['projects'], '| fresh undo:', d['undo'] == 0, '| original untouched after editing the copy:', orig == [3, None])

        # rename through the real input
        await page.evaluate("() => openJobs()")
        await page.locator('.proj.on .proj-more').click()
        await page.locator('.proj.on .proj-acts button', has_text='Rename').click()
        await page.locator('.proj-rename').fill('Farm hero shot'); await page.locator('.proj-rename').press('Enter')
        print('PR5 rename:', await page.evaluate("() => [document.getElementById('projTitle').textContent, currentProject.name]"))
        await page.keyboard.press('Escape')

        # exports nest under their projects; pause lets the next job run; the paused one resumes exactly
        await run(page, "await loadFile(new File([await makeClip()], 'clip.webm', {type:'video/webm'})); addFull(); media.speed = 'fit'; $('fps').value = 10; $('outW').value = '0'; $('dither').checked = false; refreshTotal();")
        await page.evaluate("() => { enqueueExport('gif'); }")
        await page.wait_for_function("() => jobs[0].state === 'running' && jobs[0].progress > 0.2", timeout=20000)
        await page.evaluate("() => { switchProject(projects[1]); enqueueExport('gif'); }")   # beach project queues its own
        await page.evaluate("() => pauseJob(jobs[0])")
        await page.wait_for_function("() => jobs[1].state === 'running' || jobs[1].state === 'done'", timeout=10000)
        mid = await page.evaluate("() => jobs.map(j => j.state + ':' + Math.round(j.progress * 100))")
        await page.wait_for_function("() => jobs[1].state === 'done'", timeout=30000)
        await page.evaluate("() => resumeJob(jobs[0])")
        await page.wait_for_function("() => jobs[0].state === 'done'", timeout=60000)
        seq = await page.evaluate("""async () => { const g = await decodeGif(new Uint8Array(await jobs[0].blob.arrayBuffer()));
            return g.frames.map(f => which(f.canvas.getContext('2d').getImageData(g.width/2|0, g.height/2|0, 1, 1).data)); }""")
        print('PR6 pause → other job ran:', mid, '| resumed job exact:', seq == list(range(20)))
        nest = await page.evaluate("() => { openJobs(); return projects.map(p => [p.name, projectJobs(p).length, document.querySelectorAll('#jobList .exports .job').length]); }")
        print('   nested in sheet:', nest)
        await page.keyboard.press('Escape')

        # close with running exports: let them finish → project leaves when they're done
        await page.evaluate("() => { switchProject(projects.find(p => p.name.startsWith('Farm hero'))); $('outW').value = '0'; refreshTotal(); enqueueExport('gif'); }")
        await page.wait_for_function("() => jobs[2].state === 'running'", timeout=20000)
        await page.evaluate("() => { openJobs(); closeProject(currentProject); }")
        confirm = await page.evaluate("() => !!document.querySelector('.proj-confirm')")
        await page.evaluate("() => closeProject(projects.find(p => p.confirmClose), 'finish')")
        during = await page.evaluate("() => projects.map(p => p.name + (p.closing ? '[closing]' : '') + (p === currentProject ? '*' : ''))")
        await page.wait_for_function("() => jobs[2].state === 'done'", timeout=60000)
        after = await page.evaluate("() => [projects.map(p => p.name), !!jobs[2].blob]")
        print('PR7 close with running export: confirm shown', confirm, '| during', during, '| after', after)
        await page.keyboard.press('Escape')

        # close with "stop": job cancelled, project gone; closing the last project leaves a fresh Untitled
        await page.evaluate("() => { enqueueExport('gif'); }")
        await page.wait_for_function("() => jobs[3].state === 'running'", timeout=20000)
        await page.evaluate("() => { closeProject(currentProject); closeProject(currentProject, 'stop'); }")
        await page.wait_for_function("() => !jobRunning", timeout=20000)
        st = await page.evaluate("() => [jobs[3].state, projects.map(p => p.name)]")
        await page.evaluate("() => { for (let k = 0; k < 6 && !(projects.length === 1 && !src); k++) closeProject(currentProject); }")
        last = await page.evaluate(STATE)
        print('PR8 stop + close:', st, '| closing every project leaves:', last['projects'], 'empty:', last['emptyShown'], 'title:', last['title'])

        # loading a project file while this project has media opens it as a new project
        await run(page, "await loadFile(await makeImage(800, 450, 'a.png')); shots.push(fitRect(300, 200, 200, 0)); refreshTotal(); window.P = await buildProject(true);")
        await page.evaluate("async () => { const f = new File([JSON.stringify(P)], 'a.dolly.json', {type:'application/json'}); const dt = new DataTransfer(); dt.items.add(f); const inp = document.getElementById('projFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change')); }")
        await page.wait_for_function("() => projects.length === 2 && src", timeout=10000)
        print('PR9 project file opened as a new project:', await page.evaluate("() => projects.map(p => p.name + (p === currentProject ? '*' : ''))"))
        await b.close()

        # phone: header switcher + Projects sheet with nested exports
        b = await p.chromium.launch(executable_path=CHROMIUM)
        m = await b.new_page(viewport={'width':390,'height':844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        await m.goto(URL); await m.evaluate(IMG)
        await run(m, "await loadFile(await makeImage(1600, 900, 'farm.png')); shots.push(fitRect(500, 300, 400, 0)); refreshTotal(); $('outW').value = '480'; $('fps').value = 12; enqueueExport('gif'); newProject(false); await loadFile(await makeImage(900, 1200, 'portrait.png')); shots.push(fitRect(450, 500, 400, 0)); refreshTotal(); $('outW').value = '480'; $('vidFmt').value = 'webm'; enqueueExport('webm'); enqueueExport('gif');")
        await m.wait_for_function("() => jobs[0].state === 'done' && jobs[1].state === 'running' && jobs[1].progress > .2", timeout=60000)
        await m.evaluate("() => pauseJob(jobs[1])")
        await m.locator('#btnProjects').click(); await m.wait_for_timeout(300)
        await m.screenshot(path=OUT + '/proj_sheet.png')
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
