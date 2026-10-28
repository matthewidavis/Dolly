from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio, json
from playwright.async_api import async_playwright
EXE = CHROMIUM
IMG = open('projtest.py').read().split('IMG = r"""')[1].split('"""')[0]
KEY = "() => JSON.stringify([shots.map(s => [Math.round(s.x), Math.round(s.y), Math.round(s.w), +(s.rot||0).toFixed(3), !!s.full, s.dwell ?? null, s.out ?? null]), defaults(), media, src && src.name])"
async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=EXE)
        page = await b.new_page(viewport={'width':1100,'height':950})
        page.on('pageerror', lambda e: errs.append(str(e)))
        await page.goto(URL); await page.evaluate(IMG)
        tick = lambda: page.evaluate("() => new Promise(r => setTimeout(r, 20))")
        await page.evaluate("async () => loadFile(await makeImage(1600, 900, 'a.png'))"); await tick()
        states = [await page.evaluate(KEY)]
        print('U0 after first load: undo depth', await page.evaluate("undoStack.length"), '(expect 0)')

        box = await page.locator('#vf').bounding_box()
        async def drag(x0, y0, x1, y1):
            await page.mouse.move(box['x']+x0, box['y']+y0); await page.mouse.down()
            await page.mouse.move(box['x']+x1, box['y']+y1, steps=12); await page.mouse.up(); await tick()
        # a series of distinct edits
        await drag(200, 120, 420, 260); states.append(await page.evaluate(KEY))                    # draw shot 2
        await drag(300, 180, 360, 220); states.append(await page.evaluate(KEY))                    # move it (12 pointer moves)
        await page.evaluate("() => { setOut(0, 'kind', 'fade'); refreshTotal(); }"); await tick(); states.append(await page.evaluate(KEY))
        await page.evaluate("() => selectShot(1)"); await tick()                                     # selection only: no step
        await page.evaluate("() => { const r = document.querySelector('#inspector input[type=range]'); for (const v of [0.8,1.1,1.5,2.0,2.4]){ r.value = v; r.dispatchEvent(new Event('input')); } r.dispatchEvent(new Event('change')); }"); await tick()
        states.append(await page.evaluate(KEY))                                                      # dwell slider: one step
        await page.evaluate("async () => { const d = $('dur'); for (const v of [3.5,4,5,6,7,8]){ d.value = v; d.dispatchEvent(new Event('input')); await new Promise(r => setTimeout(r, 30)); } }"); await tick()
        states.append(await page.evaluate(KEY))                                                      # Defaults slider stream: one step
        await page.evaluate("() => { levelShot(1); }"); await tick()                                 # no-op level (already level): no step
        await page.evaluate("() => deleteShot(1)"); await tick(); states.append(await page.evaluate(KEY))
        link = await page.evaluate("() => !!document.querySelector('#status .undo-link')")
        depth = await page.evaluate("undoStack.length")
        print('U1 steps recorded:', depth, '(expect', len(states) - 1, ') | Undo link after delete:', link)

        # undo all the way back, checking each state; then redo all the way forward
        ok_back = True
        for i in range(len(states) - 2, -1, -1):
            await page.keyboard.press('Control+z'); await tick()
            if await page.evaluate(KEY) != states[i]: ok_back = False; print('   undo mismatch at', i)
        print('U2 Ctrl+Z walks back through every state:', ok_back, '| left:', await page.evaluate("undoStack.length"))
        ok_fwd = True
        for i in range(1, len(states)):
            await page.keyboard.press('Control+Shift+z'); await tick()
            if await page.evaluate(KEY) != states[i]: ok_fwd = False; print('   redo mismatch at', i)
        print('U3 Ctrl+Shift+Z walks forward again:', ok_fwd)

        # Undo link restores a deleted shot; a new edit clears redo
        await page.evaluate("() => { shots.push(fitRect(800, 400, 300, 0)); refreshTotal(); }"); await tick()
        await page.evaluate("() => deleteShot(1)"); await tick()
        await page.locator('#status .undo-link').click(); await tick()
        print('U4 Undo link brings the shot back:', await page.evaluate("shots.length"), 'shots | status:', await page.evaluate("() => document.getElementById('status').textContent"))
        await page.keyboard.press('Control+z'); await tick()
        await page.evaluate("() => { setOut(0, 'dur', 9); refreshTotal(); }"); await tick()
        print('U5 new edit clears redo:', await page.evaluate("redoStack.length") == 0)

        # replacing the media is undoable (previous image + its shots come back)
        before = await page.evaluate(KEY)
        await page.evaluate("async () => loadFile(await makeImage(900, 900, 'b.png'))"); await tick()
        swapped = await page.evaluate("() => [src.name, src.w, shots.length, !!document.querySelector('#status .undo-link')]")
        await page.keyboard.press('Control+z'); await tick()
        back = await page.evaluate(KEY)
        print('U6 open new media:', swapped, '→ undo restores previous image and shots:', back == before, await page.evaluate("() => [src.name, vf.width, vf.height]"))
        await page.keyboard.press('Control+Shift+z'); await tick()
        print('   redo returns to the new image:', await page.evaluate("() => [src.name, shots.length]"))

        # a project that brings its own media is ONE undo step
        await page.keyboard.press('Control+z'); await tick()
        before = await page.evaluate(KEY); d0 = await page.evaluate("undoStack.length")
        proj = await page.evaluate("async () => { const f = await makeImage(640, 480, 'c.png'); const saved = src, file = srcFile;"
                                   "  srcFile = f; const p = await buildProject(true); srcFile = file; p.shots.push({cx:.5,cy:.5,wf:.3,rot:0}); return p; }")
        await page.evaluate("async (j) => loadFile(new File([JSON.stringify(j)], 'c.dolly.json', {type:'application/json'}))", proj); await page.wait_for_timeout(300)
        mid = await page.evaluate("() => [src.name, src.w, shots.length, undoStack.length]")
        await page.keyboard.press('Control+z'); await tick()
        print('U7 embedded-media project:', mid, '| one step:', mid[3] == d0 + 1, '| undo restores everything:', await page.evaluate(KEY) == before)

        # selection that no longer exists is dropped cleanly
        await page.evaluate("() => { selectShot(shots.length - 1); }"); await tick()
        r = await page.evaluate("() => { shots.splice(1); refreshTotal(); return 0; }"); await tick()
        await page.keyboard.press('Control+z'); await tick(); await page.keyboard.press('Control+Shift+z'); await tick()
        print('U8 restored selection valid:', await page.evaluate("() => activeShot < shots.length && (activeShot < 0 || !!shots[activeShot])"))

        # cap at 100 steps
        await page.evaluate("async () => { for (let i = 0; i < 130; i++){ setOut(0, 'dur', 1 + (i % 50) * 0.2); refreshTotal(); await Promise.resolve(); await new Promise(r => setTimeout(r, 0)); } }"); await tick()
        print('U9 history capped:', await page.evaluate("undoStack.length"), '(max 100)')

        # mobile: status Undo link is tappable
        m = await b.new_page(viewport={'width':390,'height':844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        await m.goto(URL); await m.evaluate(IMG)
        await m.evaluate("async () => { await loadFile(await makeImage(1600, 900, 'a.png')); shots.push(fitRect(500,300,400,0)); refreshTotal(); }"); await m.wait_for_timeout(50)
        await m.evaluate("() => deleteShot(1)"); await m.wait_for_timeout(50)
        await m.locator('#status .undo-link').tap(); await m.wait_for_timeout(50)
        print('U10 phone: tap Undo restores:', await m.evaluate("shots.length"), 'shots')
        await m.evaluate("() => deleteShot(1)"); await m.wait_for_timeout(50)
        await m.screenshot(path=OUT + '/undo_mobile.png')
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
