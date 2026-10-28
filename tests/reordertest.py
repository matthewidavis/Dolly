from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio
from playwright.async_api import async_playwright
EXE = CHROMIUM
IMG = open('projtest.py').read().split('IMG = r"""')[1].split('"""')[0]
# each shot tagged by its dwell so we can read the order back: FULL=0.5(default), then 1.1, 1.2, 1.3, ...
SETUP = """async (n) => { await loadFile(await makeImage(1600, 900, 'a.png'));
  for (let k = 1; k < n; k++){ const s = fitRect(200 + k * 150, 300 + (k % 3) * 120, 300, 0); s.dwell = +(1 + k / 10).toFixed(1); shots.push(s); }
  setOut(2, 'kind', 'fade'); refreshTotal(); }"""
ORDER = "() => shots.map(s => s.full ? 'F' : String(s.dwell))"
async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=EXE)
        # ---------------- desktop mouse ----------------
        page = await b.new_page(viewport={'width':1100,'height':950})
        page.on('pageerror', lambda e: errs.append(str(e)))
        await page.goto(URL); await page.evaluate(IMG); await page.evaluate(SETUP, 4)
        await page.wait_for_timeout(120); await page.evaluate("""() => { const sc = document.getElementById('tlScroll'); sc.scrollLeft = parseFloat(getComputedStyle(sc).getPropertyValue('--pad')) || 0; }"""); await page.wait_for_timeout(120)
        o0 = await page.evaluate(ORDER); depth0 = await page.evaluate("undoStack.length")
        cards = page.locator('.card')
        a = await cards.nth(3).bounding_box(); t = await cards.nth(1).bounding_box()
        await page.mouse.move(a['x'] + a['width']/2, a['y'] + a['height']/2); await page.mouse.down()
        for k in range(1, 21):
            x = a['x'] + a['width']/2 + (t['x'] + t['width']*0.3 - a['x'] - a['width']/2) * k / 20
            await page.mouse.move(x, a['y'] + a['height']/2); await page.wait_for_timeout(15)
        mid = await page.evaluate("() => ({ ghost: !!document.querySelector('.card-ghost'), dragging: document.querySelectorAll('.card.dragging').length })")
        await page.mouse.up(); await page.wait_for_timeout(80)
        o1 = await page.evaluate(ORDER)
        fade = await page.evaluate("() => shots.findIndex(s => s.out && s.out.kind === 'fade')")
        print('R1 mouse drag card 4 → slot 2:', o0, '→', o1, '| mid-drag', mid, '| fade move travels with its shot (now index', fade, ')')
        print('   one undo step:', await page.evaluate("undoStack.length") - depth0 == 1, '| selected:', await page.evaluate("activeShot"),
              '| inspector buttons:', await page.evaluate("() => [...document.querySelectorAll('#inspector .actions button')].map(b => b.textContent)"))
        await page.keyboard.press('Control+z'); await page.wait_for_timeout(50)
        print('R2 Ctrl+Z restores order:', await page.evaluate(ORDER) == o0)
        await cards.nth(2).click(); await page.wait_for_timeout(50)
        print('R3 plain click selects, no reorder:', await page.evaluate("activeShot"), await page.evaluate(ORDER) == o0)

        # ---------------- phone touch ----------------
        ctx = await b.new_context(viewport={'width':390,'height':844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        m = await ctx.new_page(); m.on('pageerror', lambda e: errs.append('phone: ' + str(e)))
        await m.goto(URL); await m.evaluate(IMG); await m.evaluate(SETUP, 7); await m.wait_for_timeout(50)
        cdp = await ctx.new_cdp_session(m)
        async def touch(kind, x, y):
            pts = [] if kind == 'touchEnd' else [{'x': x, 'y': y}]
            await cdp.send('Input.dispatchTouchEvent', {'type': kind, 'touchPoints': pts})
        async def card_center(k):
            bb = await m.locator('.card').nth(k).bounding_box(); return bb['x'] + bb['width']/2, bb['y'] + bb['height']/2

        o0 = await m.evaluate(ORDER)
        # quick swipe left with no hold: strip scrolls, nothing moves
        x, y = await card_center(1); s0 = await m.evaluate("() => document.getElementById('tlScroll').scrollLeft")
        await touch('touchStart', x, y)
        for k in range(1, 9): await touch('touchMove', x - k * 25, y); await m.wait_for_timeout(12)
        await touch('touchEnd', 0, 0); await m.wait_for_timeout(250)
        s1 = await m.evaluate("() => document.getElementById('tlScroll').scrollLeft")
        print('R4 swipe (no hold): strip scrolled', round(s0), '→', round(s1), '| order unchanged:', await m.evaluate(ORDER) == o0)
        await m.evaluate("""() => { const sc = document.getElementById('tlScroll'); sc.scrollLeft = parseFloat(getComputedStyle(sc).getPropertyValue('--pad')) || 0; }"""); await m.wait_for_timeout(120)

        # tap selects
        x, y = await card_center(2)
        await touch('touchStart', x, y); await m.wait_for_timeout(60); await touch('touchEnd', 0, 0); await m.wait_for_timeout(120)
        print('R5 tap selects:', await m.evaluate("activeShot"), '| order unchanged:', await m.evaluate(ORDER) == o0)

        # hold, then drag card 1 to the right past card 2
        x, y = await card_center(1); xt, _ = await card_center(2)
        pre = await m.evaluate("() => ({ cardDrag: !!cardDrag, scroll: document.getElementById('tlScroll').scrollLeft, active: activeShot })")
        print('   before R6:', pre, 'card1 x', round(x), 'card2 x', round(xt))
        await touch('touchStart', x, y); await m.wait_for_timeout(450)
        lifted = await m.evaluate("() => !!(cardDrag && cardDrag.lifted)")
        for k in range(1, 13): await touch('touchMove', x + (xt - x + 30) * k / 12, y); await m.wait_for_timeout(16)
        await touch('touchEnd', 0, 0); await m.wait_for_timeout(250)
        o1 = await m.evaluate(ORDER)
        print('R6 hold + drag:', 'lifted' if lifted else 'NOT lifted', o0, '→', o1, '| page scrolled?', await m.evaluate("() => window.scrollY"))
        await m.evaluate("() => undo()"); await m.wait_for_timeout(60)
        print('   undo restores:', await m.evaluate(ORDER) == o0)

        # auto-scroll: hold card 0, drag to the right edge and wait
        await m.evaluate("""() => { const sc = document.getElementById('tlScroll'); sc.scrollLeft = parseFloat(getComputedStyle(sc).getPropertyValue('--pad')) || 0; }"""); await m.wait_for_timeout(120)
        x, y = await card_center(0)
        await touch('touchStart', x, y); await m.wait_for_timeout(450)
        edge = await m.evaluate("() => document.getElementById('tlScroll').getBoundingClientRect().right")
        for k in range(1, 9): await touch('touchMove', x + (edge - 8 - x) * k / 8, y); await m.wait_for_timeout(16)
        sA = await m.evaluate("() => document.getElementById('tlScroll').scrollLeft")
        for k in range(30): await touch('touchMove', edge - 8 + (k % 2), y); await m.wait_for_timeout(30)
        sB = await m.evaluate("() => document.getElementById('tlScroll').scrollLeft")
        await m.screenshot(path=OUT + '/reorder_mobile.png')
        await touch('touchEnd', 0, 0); await m.wait_for_timeout(250)
        print('R7 auto-scroll at edge:', round(sA), '→', round(sB), '| first card carried to index', await m.evaluate("() => shots.findIndex(s => s.full)"), 'of', await m.evaluate("shots.length"))
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
