from kitconf import URL, REFERENCE_URL, CHROMIUM, CHROME_H264, OUT
import asyncio
from playwright.async_api import async_playwright
IMG = open('auditshots.py').read().split('IMG = r"""')[1].split('"""')[0]
AUD = open('soundtest.py').read().split('AUD = r"""')[1].split('"""')[0]
ST = "() => ({ playing: !!previewRAF, userPaused, t: +viewT.toFixed(2), sound: !!previewSound, label: $('btnPreview').getAttribute('aria-label') })"
async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROMIUM)
        ctx = await b.new_context(viewport={'width':390,'height':844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        await ctx.add_init_script("window.__dollyAutoplay = true;")
        m = await ctx.new_page(); m.on('pageerror', lambda e: errs.append(str(e)))
        await m.goto(URL); await m.evaluate(IMG); await m.evaluate(AUD)
        await m.evaluate("() => { setTimeout(async () => { await loadFile(await photo()); shots.push(fitRect(1050, 470, 380, 0), fitRect(330, 300, 520, 0)); deselect(); await addTrack(makeWav(2, 660)); window.__a = 1; }, 0); }")
        await m.wait_for_function("() => window.__a"); await m.wait_for_timeout(900)
        a1 = await m.evaluate(ST); print('A1 plays on its own after opening, muted:', a1['playing'] and not a1['sound'], a1)
        tot = await m.evaluate("() => curTL.total")
        await m.wait_for_timeout(int(tot * 1000) + 600)
        a2 = await m.evaluate(ST); print('A2 loops past the end (total', tot, 's):', a2['playing'] and a2['t'] < tot, a2)
        # selecting a shot pauses it for editing; Done resumes
        await m.locator('.card').nth(1).tap(); await m.wait_for_timeout(350)
        a3 = await m.evaluate(ST)
        await m.locator('#toolDone').tap(); await m.wait_for_timeout(700)
        a3b = await m.evaluate(ST)
        print('A3 select pauses:', not a3['playing'], '| Done resumes:', a3b['playing'])
        # ❚❚ holds through Done-style events until ▶
        await m.locator('#btnPreview').tap(); await m.wait_for_timeout(200)
        await m.locator('.card').nth(1).tap(); await m.wait_for_timeout(200); await m.locator('#toolDone').tap(); await m.wait_for_timeout(800)
        a4 = await m.evaluate(ST)
        await m.locator('#btnPreview').tap(); await m.wait_for_timeout(300)
        print('A4 explicit pause holds after Done:', not a4['playing'] and a4['userPaused'], '| ▶ resumes:', (await m.evaluate(ST))['playing'])
        # touching the picture pauses for editing (not a hold)
        r = await m.evaluate("() => { const b = vf.getBoundingClientRect(); return [b.left + 20, b.top + 20]; }")
        await m.touchscreen.tap(r[0], r[1]); await m.wait_for_timeout(250)
        a5 = await m.evaluate(ST); print('A5 touching the picture pauses:', not a5['playing'], '(hold:', a5['userPaused'], ')')
        await m.locator('#btnPreview').tap(); await m.wait_for_timeout(300)
        # sound toggle: on, remembered
        await m.locator('#btnMute').tap(); await m.wait_for_timeout(400)
        a6 = await m.evaluate(ST); stored = await m.evaluate("() => localStorage.getItem('dolly-sound')")
        print('A6 speaker turns sound on mid-play:', a6['playing'] and a6['sound'], '| remembered:', stored)
        await m.screenshot(path=OUT + '/ap_phone.png')
        # no autostart while an export runs
        await m.locator('#btnPreview').tap(); await m.evaluate("() => { userPaused = false; $('outW').value = '1280'; $('fps').value = 30; $('vidFmt').value = 'webm'; enqueueExport('webm'); }")
        await m.wait_for_timeout(200); await m.evaluate("() => { maybeAutoplay(); }"); await m.wait_for_timeout(200)
        a7 = await m.evaluate(ST); print('A7 no autostart during an export:', not a7['playing'], '| job running:', await m.evaluate("() => !!jobRunning"))
        await b.close()
        # automated runs without the opt-in don't autoplay (the existing suites rely on still frames)
        b = await p.chromium.launch(executable_path=CHROMIUM)
        d = await b.new_page(); await d.goto(URL); await d.evaluate(IMG)
        await d.evaluate("() => { setTimeout(async () => { await loadFile(await photo()); shots.push(fitRect(1050, 470, 380, 0)); deselect(); window.__a = 1; }, 0); }")
        await d.wait_for_function("() => window.__a"); await d.wait_for_timeout(900)
        print('A8 without the opt-in, no autoplay:', not await d.evaluate("() => !!previewRAF"))
        await b.close()
    print('ERRORS:', errs or 'none')
asyncio.run(main())
