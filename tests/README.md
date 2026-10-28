# Dolly test kit

Automated checks for `dolly.html`: 32 functional suites plus a before/after pixel comparison.
They drive a real browser (Chromium, headless) through Playwright: loading media, tapping,
multi-touch gestures, playback, exports decoded back frame by frame, reloads for recovery.

## Setup

```bash
pip install playwright pillow
python -m playwright install chromium
```

In the repository these tests live in `tests/` and target `../index.html` automatically
(a standalone copy next to `dolly.html` works too). Point `DOLLY_URL` elsewhere to test another build.

## Run

```bash
./run_all.sh                 # everything (several minutes); prints "clean: 32 of 32"
./run_all.sh styletest       # one suite (or several, space-separated)
python3 cssdiff.py           # pixel comparison against reference/dolly-reference.html
```

Logs land in `out/logs/`, screenshots in `out/`. A suite is clean when it ends with `ERRORS: none`;
the lines before it describe each check and its measured result.

**Run the pixel comparison after any stylesheet change.** Functional suites have passed while
the layout was broken. It compares six screens on a phone and on desktop against the reference;
only intended changes should differ (the style preview animates, so a few hundred pixels there
are normal). When a visual change is intended, copy the new file into `reference/`.

## Settings (environment variables)

| Variable | Default | Purpose |
| --- | --- | --- |
| `DOLLY_URL` | `../index.html` (or `../dolly.html`) | the file under test |
| `DOLLY_REFERENCE_URL` | `reference/dolly-reference.html` | baseline for the pixel comparison |
| `DOLLY_CHROMIUM` | Playwright's Chromium | browser for most suites |
| `DOLLY_CHROME` | same as above | a Google Chrome build, for real MP4 (H.264) and AAC checks |
| `DOLLY_OUT` | `out/` | screenshots and logs |

Playwright's Chromium has no H.264 encoder, so without `DOLLY_CHROME` the MP4 suite skips its
checks (and says so); WebM export is covered by the other suites either way.

## What each suite covers

| Suite | Covers |
| --- | --- |
| uitest | the main flow: shots, moves, timeline layout, scrubbing, exports, phone layout |
| reordertest | dragging cards (mouse, touch hold), swipe-to-scroll, auto-scroll |
| playheadtest | fixed centre playhead: scrubbing by scrolling, playback tracking, centring |
| gesturetest | touch: tap, slop, drag, drawing on empty image, centre snap, pinch, twist, level snap |
| rotatetest | rotate knob on touch, twists with a finger off the image, edge shots |
| cornertest | touch corner handles (straight and rotated shots) |
| autoplaytest | autoplay, looping, pause/resume rules, sound toggle, export priority |
| undotest | undo/redo granularity, coalescing, media swaps |
| projtest | project files: save, load, templates on other images, hostile files |
| projectstest | several open projects: switching, duplicate, rename, close, nested exports |
| recoverytest | autosave and restore across real reloads, video reopen prompt |
| queuetest | export queue: snapshots, order, cancel, preview during export, smoothness |
| pintest | pinned shots: exact arrival, red pins, reorder |
| giftest | GIF decoding (pixel-exact) and exports from GIF sources |
| videotest | video frame mapping, trim, live preview, exports from video |
| fittest | Fit camera timing |
| naturaltest | speed modes and their defaults |
| soundtest | music, video sound, sync, AAC/Opus in MP4/WebM |
| motiontest | frame blending for speed changes |
| mp4test | MP4 structure, decode against reference renders, seeking |
| lighttest | light/dark themes, contrast, identical exports in both |
| motionpathtest | camera paths (exact endpoints, pull-back) and motion blur |
| styletest | move styles, previews, Overshoot and Whip behaviour |
| lifetest | hold styles and handheld: exact arrivals, no jumps, bounds |
| flowtest | continuous camera and the new transitions |
| leaktest | releasing videos nothing needs (and keeping ones that are) |
| arctest | flowing through zero-dwell shots on a curve, and arced moves |
| curvetest | curved paths through stopping shots (no corners, Gentle/Strong), finger drawing |
| frametest | output shapes: Fill reshaping, export size, Fit with black or blurred bars, the viewfinder |
| looktest | grade presets (measured effect), strength, grain, vignette, cinema bars, exports match preview |
| paneltest | pinned panel headers, accordion sections (one open, remembered, live summaries) |
| docktest | phone panels: one fixed height over the timeline and tray, picture and controls never covered |

## Notes

- Autoplay is off when the browser reports automation (`navigator.webdriver`), so suites see
  still frames. `autoplaytest` opts in by setting `window.__dollyAutoplay = true` first.
- Some checks measure timing or smoothness; on a busy machine they can run slow. Re-run a
  suite alone before treating a timing result as a regression.
- Timing and Look settings sit in accordion sections; a test that taps a control inside one opens it first
  (`el.closest('details').open = true`), as a person would.
- `auditshots.py` is not a suite; others borrow its photo-like test image.
- The look runs on WebGL. Headless Chromium emulates the GPU in software (SwiftShader), so looktest's
  per-frame cost (L7) is far higher there than on real hardware; it is reported, not judged.
