"""Paths for the Dolly test kit. Override any of them with environment variables."""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
# the file under test (default: the repository's index.html, one level up)
def _default_target():
    for name in ("index.html", "dolly.html"):
        path = os.path.abspath(os.path.join(HERE, "..", name))
        if os.path.exists(path): return "file://" + path
    return "file://" + os.path.abspath(os.path.join(HERE, "..", "index.html"))
URL = os.environ.get("DOLLY_URL") or _default_target()
# a reference copy for the pixel comparison (default: the one shipped in this kit)
REFERENCE_URL = os.environ.get("DOLLY_REFERENCE_URL") or "file://" + os.path.join(HERE, "reference", "dolly-reference.html")
# Chromium to drive (None = Playwright's own). Its open-source build has no H.264 encoder,
# so MP4 checks report the WebM fallback; point DOLLY_CHROME at Google Chrome to test real MP4/AAC.
CHROMIUM = os.environ.get("DOLLY_CHROMIUM") or None
CHROME_H264 = os.environ.get("DOLLY_CHROME") or CHROMIUM
# screenshots and other output
OUT = os.environ.get("DOLLY_OUT") or os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
