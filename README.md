# Dolly

Draw a frame, render the move. Turn a still image into a dolly/pan/zoom
clip — entirely in the browser.

**→ [Open Dolly](https://matthewidavis.github.io/Dolly/)**

## What it does

Load an image, draw one or more regions on it, and Dolly renders the
camera move between them as a video or GIF.

- **Shot sequence.** Each region you draw becomes a shot. Reorder them,
  duplicate one and drag the copy for a pure pan, or add the full frame
  as a wide establishing shot.
- **Transitions.** Glide (dolly), crossfade, or cut.
- **Timing.** Move duration, dwell per shot, easing, and frame rate.
- **Video export.** Uses WebCodecs where available so frames are
  timestamped exactly on the fps grid — no wall-clock stutter — muxed to
  WebM by a built-in EBML writer. Falls back to `MediaRecorder` on
  browsers without WebCodecs.
- **GIF export.** Built-in GIF89a encoder with a median-cut global
  palette and optional Floyd–Steinberg dithering.

## Install it

Dolly is a PWA, so you can install it to your home screen or desktop and
it runs standalone, without browser chrome.

- **Android / Chrome / Edge** — open the site, then "Install app" or "Add
  to Home screen" from the browser menu.
- **iOS / Safari** — Share → Add to Home Screen.

Once installed it works **fully offline**. Dolly makes no network
requests after load, so there is nothing to degrade when you lose
connectivity — the whole app is cached.

## Privacy

Everything runs client-side. Your image is never uploaded — there is no
server, no analytics, and no network request after the page loads.

## Running it locally

The app is a single self-contained HTML file with no build step and no
dependencies:

```
git clone https://github.com/matthewidavis/Dolly.git
cd Dolly
python -m http.server 8000
```

Then open `http://localhost:8000`. Serving it over HTTP (rather than
opening `index.html` directly) is what lets the service worker register,
which is also why the app still works with the server stopped.

## Deploying a change

`sw.js` caches the app, so a returning visitor is served the cached copy
until the worker sees a new version. **Bump `CACHE` in `sw.js` on every
deploy** — otherwise the change ships and nobody receives it. When the
worker does find an update, the page offers a reload rather than swapping
the code mid-render.

## Browser support

Chrome and Edge get the exact-timing WebCodecs path. Firefox and Safari
fall back to realtime recording, which still works but is timed against
the wall clock. GIF export works everywhere.
