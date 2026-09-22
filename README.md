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

## Privacy

Everything runs client-side. Your image is never uploaded — there is no
server, no analytics, and no network request after the page loads.

## Running it locally

It is a single self-contained HTML file with no build step and no
dependencies:

```
git clone https://github.com/matthewidavis/Dolly.git
cd Dolly
```

Then open `index.html` in a browser, or serve the directory:

```
python -m http.server 8000
```

## Browser support

Chrome and Edge get the exact-timing WebCodecs path. Firefox and Safari
fall back to realtime recording, which still works but is timed against
the wall clock. GIF export works everywhere.
