# Dolly

Turn a photo, GIF or video into a cinematic camera move, entirely in the browser.

**→ [Open Dolly](https://matthewidavis.github.io/Dolly/)**

## What it does

Open a picture or clip, frame a few shots on it, and Dolly animates a virtual camera
between them, then exports the result as MP4, WebM or GIF.

- **Shots.** Draw shots on the image (finger or mouse) or tap **Shot**. Move, resize and
  rotate them with handles, a rotate knob, or pinch and twist. Hold a card on the timeline
  to reorder. Moves snap to centre and level.
- **Motion that feels shot, not animated.**
  - Six move styles: Smooth, Gentle, Snap, Overshoot, Whip, Linear.
  - Curved paths (Gentle or Strong) swing through your shots instead of zig-zagging;
    a dwell of 0 makes the camera flow straight through a shot; per-move Arc left/right.
  - Natural or Sweeping camera paths pull back on long moves so the viewer keeps context.
  - Real shutter-style motion blur, living holds (push in/out, float), subtle or strong
    handheld, and a Continuous mode for one flowing flight.
  - Transitions: glide, crossfade, cut, dip to black or white, whip pan, zoom blur.
- **Look & frame.**
  - Output shapes 16:9, 9:16, 4:5, 1:1 or original: fill (shots take the frame's shape)
    or fit with black or blurred bars.
  - Grade presets (Warm film, Teal & orange, Cool night, Faded, Black & white) with
    strength, film grain, vignette and 2.39:1 cinema bars.
- **GIFs and video.** Speed presets and fit modes, trim on a filmstrip, frame blending
  for slow or fast motion, pinned shots that land on an exact moment of the clip.
- **Sound.** Keep the clip's sound and/or add music, with volume, start, loop and fade.
- **Projects.** Several open at once, each with its own undo. Exports queue in the
  background (pause, stop, resume) while you keep working. Open projects are saved on
  the device and come back after a reload. Projects can be saved as small files and
  reused as templates on other images.

## On desktop

At 1000px and wider the same app lays out for a big screen: tools in a rail on the left,
the picture using the whole window, and a side panel that shows the selected shot or move,
or the project's Timing and Look settings when nothing is selected.

| Key | Action |
| --- | --- |
| Space | Play / pause |
| ← ↑ → ↓ | Nudge the selected shot (Shift: ×10) |
| Delete | Remove the selected shot |
| Ctrl/⌘ + D | Duplicate the selected shot |
| Ctrl/⌘ + Z, Shift + Ctrl/⌘ + Z | Undo, redo |
| Esc | Close the panel / deselect |

## Install it

Dolly is a PWA, so you can install it to your home screen or desktop and it runs
standalone, without browser chrome.

- **Android / Chrome / Edge**: open the site, then "Install app" or "Add to Home screen"
  from the browser menu.
- **iOS / Safari**: Share → Add to Home Screen.

Once installed it works **fully offline**. Dolly makes no network requests after load,
so there is nothing to degrade when you lose connectivity: the whole app is cached.

## Privacy

Everything runs client-side. Your pictures and videos are never uploaded: there is no
server, no analytics, and no network request after the page loads. Autosaved projects
stay in your browser's own storage on your device.

## Running it locally

The app is a single self-contained HTML file with no build step and no dependencies:

```
git clone https://github.com/matthewidavis/Dolly.git
cd Dolly
python -m http.server 8000
```

Then open `http://localhost:8000`. Serving it over HTTP (rather than opening
`index.html` directly) is what lets the service worker register, which is also why the
app still works with the server stopped.

## Deploying a change

`sw.js` caches the app, so a returning visitor is served the cached copy until the
worker sees a new version. **Bump `CACHE` in `sw.js` on every deploy**, otherwise the
change ships and nobody receives it. When the worker does find an update, the page
offers a reload rather than swapping the code mid-edit. Reloading is safe: open
projects are autosaved, and Dolly warns first if an export is unfinished.

## Working on the code

`index.html` documents itself:

- **A guide for people** at the top of the file: layout, data flow, data shapes,
  step-by-step recipes for common changes, and the design principles.
- **Notes for AI models** at the top of the script: the state model, invariants,
  and the traps that have caused real bugs. If you hand the file to an AI assistant,
  point it at both, and at the tests.

## Tests

`tests/` holds 33 automated suites (Playwright, headless Chromium) plus a before/after
pixel comparison. See [`tests/README.md`](tests/README.md).

```
pip install playwright pillow
python -m playwright install chromium
cd tests && ./run_all.sh          # prints "clean: 33 of 33"
```

Run them before every push; run `python3 cssdiff.py` after any stylesheet change.

## Browser support

Chrome and Edge get the full feature set, including frame-exact MP4 (H.264 + AAC) and
WebM export through WebCodecs (tested). Other browsers get whatever their WebCodecs
support allows; where it's missing, video export falls back to recording the preview in
real time (without sound). GIF export works everywhere.
