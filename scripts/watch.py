#!/usr/bin/env python
"""Rebuild the model whenever you save, and serve the viewer.

    uv run watch

Leave it running and open http://localhost:4173. Edit any file under
src/turntable, save, and the page reloads with the new geometry a second or
two later.

Importing build123d costs several seconds, so this keeps one process alive
and reloads only the turntable modules on each change. That is what makes
the loop quick enough to actually design in.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
import traceback
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
WATCHED = [ROOT / "src" / "turntable", ROOT / "scripts"]
RELOADABLE = ("turntable", "scripts.export_model", "scripts.verify")


class Handler(SimpleHTTPRequestHandler):
    """Static files, never cached, and quiet about it."""

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()

    def log_message(self, *args) -> None:  # noqa: D102 - too chatty otherwise
        pass


def fingerprint() -> dict[Path, float]:
    """Modification times of everything worth rebuilding for."""
    stamps = {}
    for folder in WATCHED:
        for path in folder.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            try:
                stamps[path] = path.stat().st_mtime
            except OSError:
                pass
    return stamps


def reload_modules() -> None:
    """Drop our own modules so the next import picks up the edits.

    build123d stays loaded, which is the whole point.
    """
    for name in list(sys.modules):
        if name in RELOADABLE or any(name.startswith(f"{m}.") for m in RELOADABLE):
            del sys.modules[name]


def rebuild(quality: str, check: bool) -> bool:
    reload_modules()
    from scripts.export_model import write_web_assets

    start = time.perf_counter()
    out = write_web_assets(quality)
    built = time.perf_counter() - start

    failures = 0
    if check:
        from scripts.verify import run_checks

        failures = run_checks(quiet=True)

    size = out.stat().st_size / 1024
    status = "ok" if not failures else f"{failures} CHECK(S) FAILED"
    print(
        f"  rebuilt in {built:4.1f}s   {size:5.0f} kB   {status}",
        flush=True,
    )
    return not failures


def serve(port: int) -> None:
    handler = partial(Handler, directory=str(WEB))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"  viewer   http://localhost:{port}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=4173)
    ap.add_argument("--quality", default="normal", choices=["draft", "normal", "high"])
    ap.add_argument("--no-check", action="store_true", help="skip the geometry checks")
    ap.add_argument("--no-serve", action="store_true", help="rebuild only")
    args = ap.parse_args()

    print("\n  loading build123d...", flush=True)
    import build123d  # noqa: F401  (paid once, kept warm)

    if not args.no_serve:
        serve(args.port)
    print("  watching  src/turntable\n")

    rebuild(args.quality, not args.no_check)
    stamps = fingerprint()

    try:
        while True:
            time.sleep(0.4)
            current = fingerprint()
            if current == stamps:
                continue
            stamps = current
            changed = time.strftime("%H:%M:%S")
            print(f"\n[{changed}] change detected", flush=True)
            try:
                rebuild(args.quality, not args.no_check)
            except Exception:
                # A typo in params.py should not take the watcher down.
                traceback.print_exc()
                print("  build failed, still watching", flush=True)
    except KeyboardInterrupt:
        print("\n  stopped\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
