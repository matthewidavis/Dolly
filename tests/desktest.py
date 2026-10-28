from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio
from playwright.async_api import async_playwright
IMG = open('auditshots.py').read().split('IMG = r"""')[1].split('"""')[0]
async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROMIUM)
        m = await b.new_page(viewport={'width': 1440, 'height': 900}); m.on('pageerror', lambda e: errs.append(str(e)))
        await m.goto(URL); await m.evaluate(IMG)
        await m.evaluate("() => { setTimeout(async () => { await loadFile(await photo()); shots.push(fitRect(1050, 470, 380, 0), fitRect(330, 300, 520, 0)); deselect(); document.getElementById('status').classList.remove('show'); window.__a = 1; }, 0); }")
        await m.wait_for_function("() => window.__a"); await m.wait_for_timeout(300)
        r = await m.evaluate("""() => { const t = $('actionbar').getBoundingClientRect(), c = vf.getBoundingClientRect(), i = $('inspector').getBoundingClientRect();
            return { railLeftAndTall: t.left === 0 && t.width < 100 && t.height > 600, pictureW: Math.round(c.width), panelTitle: document.querySelector('#inspector .insp-head span').textContent,
                     sections: [...document.querySelectorAll('#inspector details.acc')].map(d => d.dataset.key).join(','), noMargins: document.body.getBoundingClientRect().width === innerWidth }; }""")
        print('K1 layout:', r)
        await m.locator('#inspector details.acc[data-key=moves] summary').click(); await m.wait_for_timeout(150)
        await m.locator('#inspector details.acc[data-key=color] summary').click(); await m.wait_for_timeout(150)
        print('K2 one section open across Timing and Look:', await m.evaluate("() => [...document.querySelectorAll('#inspector details.acc')].filter(d => d.open).map(d => d.dataset.key)"))
        await m.evaluate("() => selectShot(1)"); await m.wait_for_timeout(200)
        r = await m.evaluate("() => ({ mainToolsShown: !$('trayMain').hidden, shotToolsHidden: getComputedStyle($('trayShotSet')).display === 'none', panel: document.querySelector('#inspector .insp-head span').textContent, panelHasDelete: [...document.querySelectorAll('#inspector button')].some(b => b.textContent === 'Delete') })")
        print('K3 shot selected:', r)
        # keyboard
        await m.mouse.click(5, 880)   # focus the page, away from controls
        before = await m.evaluate("() => { const c = ctr(shots[1]); return [c.cx, c.cy, scale]; }")
        await m.keyboard.press('ArrowRight'); await m.keyboard.press('Shift+ArrowDown'); await m.wait_for_timeout(100)
        after = await m.evaluate("() => { const c = ctr(shots[1]); return [c.cx, c.cy]; }")
        print('K4 arrows nudge (1 screen px, Shift = 10): moved', round((after[0] - before[0]) * before[2], 2), 'and', round((after[1] - before[1]) * before[2], 2), 'screen px')
        await m.keyboard.press('Control+z'); await m.wait_for_timeout(100)
        print('   one undo reverts both nudges:', await m.evaluate("(b) => { const c = ctr(shots[1]); return Math.abs(c.cx - b[0]) < 1e-6 && Math.abs(c.cy - b[1]) < 1e-6; }", before))
        n = await m.evaluate("() => shots.length"); await m.keyboard.press('Control+d'); await m.wait_for_timeout(100)
        n2 = await m.evaluate("() => [shots.length, activeShot]"); await m.keyboard.press('Delete'); await m.wait_for_timeout(100)
        print('K5 Ctrl+D duplicates:', n, '→', n2[0], '| Delete removes it:', await m.evaluate("() => shots.length"))
        await m.evaluate("() => deselect()"); await m.keyboard.press(' '); await m.wait_for_timeout(300)
        p1 = await m.evaluate("() => !!previewRAF"); await m.keyboard.press(' '); await m.wait_for_timeout(150)
        print('K6 Space plays then pauses:', p1, await m.evaluate("() => !previewRAF"))
        # a focused tray button: Space still means play, not "press this button"
        await m.locator('#traySound').focus(); await m.keyboard.press(' '); await m.wait_for_timeout(250)
        print('   with a rail button focused, Space plays and the button is not pressed:', await m.evaluate("() => !!previewRAF && !selSound")); await m.evaluate("() => stopPreview()")
        # ignored while adjusting a slider
        await m.evaluate("() => selectShot(1)"); await m.wait_for_timeout(150)
        await m.locator('#inspector input[type=range]').first.focus()
        b2 = await m.evaluate("() => [ctr(shots[1]).cx, shots.length]"); await m.keyboard.press('ArrowRight'); await m.keyboard.press('Delete'); await m.wait_for_timeout(100)
        print('K7 with a slider focused, arrows/Delete leave the shot alone:', await m.evaluate("(b) => ctr(shots[1]).cx === b[0] && shots.length === b[1]", b2))
        # resize to phone width and back
        print('   and arrows keep adjusting the slider:', await m.evaluate("() => document.activeElement && document.activeElement.type === 'range'"))
        await m.evaluate("() => { document.activeElement.blur(); selectShot(1); }")
        await m.set_viewport_size({'width': 390, 'height': 844}); await m.wait_for_timeout(400)
        ph = await m.evaluate("() => ({ shotTools: !$('trayShotSet').hidden && getComputedStyle($('trayShotSet')).display !== 'none', mainHidden: $('trayMain').hidden, trayAtBottom: $('actionbar').getBoundingClientRect().bottom >= innerHeight - 1, stillSelected: activeShot === 1 })")
        await m.set_viewport_size({'width': 1440, 'height': 900}); await m.wait_for_timeout(400)
        dk = await m.evaluate("() => ({ mainShown: !$('trayMain').hidden, panel: document.querySelector('#inspector .insp-head span').textContent })")
        print('K8 resize to phone: phone shot tools', ph, '| back to desktop:', dk)
        await m.evaluate("() => { deselect(); openJobs(); }"); await m.wait_for_timeout(250)
        print('K9 Projects opens on the left:', await m.evaluate("() => { const r = $('dlgJobs').getBoundingClientRect(); return r.left < 200 && r.width > 600; }"))
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
