#!/usr/bin/env python3
"""Q239 -- a small HTTP server that MIMICS hosting differences of the published (claude.ai artifact) pages, for the imaging / ultrasound load checks.

    serve(root, **opts) -> (server, port)         then open  http://127.0.0.1:PORT/<page>   (or /__outer.html for the iframe variants)

Options (all independent, combine freely):
  mime="plain"          every .js / .json / .txt (not the page) is sent as text/plain (a host that does not know the extensions)
  nosniff=True          + X-Content-Type-Options: nosniff (then Chromium refuses to run a <script src> served as text/plain)
  wrap=True             the page is wrapped like the artifact service does (scripts/platform_wrap.py: doctype / head / <style> / body, page nested in <body>)
  cors=True             Access-Control-Allow-Origin: * (needed for fetch() from an opaque-origin sandboxed iframe)
  hide=("clinical_",)   path prefixes answered with 404 (no sibling files at all = inline only)
  sandbox=None|"allow-scripts"|"allow-scripts allow-same-origin"   /__outer.html = an <iframe sandbox=...> around the page (the artifact viewer's frame)
  csp="..."             Content-Security-Policy header on the page (e.g. script-src without blob: = no Web Worker from a Blob)
  srcdoc=False          /__outer.html uses <iframe srcdoc=page> with a <base href> (no real URL for the frame itself)
"""
from __future__ import annotations

import html as _html
import http.server
import mimetypes
import socket
import threading
from pathlib import Path

SKELETON_PRE = '<!doctype html><html><head><meta charset=utf8><meta name=viewport content="width=device-width,initial-scale=1"><style>html,body{margin:0;height:100%}</style></head><body>\n'
SKELETON_SUF = "\n</body></html>"


def make_handler(root: Path, mime=None, nosniff=False, wrap=False, cors=False, hide=(), sandbox=None, srcdoc=False, page="index.html", log=None, csp=None):
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(root), **k)

        def log_message(self, *a):
            pass

        def _send(self, code, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            if cors or sandbox is not None:
                self.send_header("Access-Control-Allow-Origin", "*")
            if nosniff:
                self.send_header("X-Content-Type-Options", "nosniff")
            if csp and ctype.startswith("text/html"):
                self.send_header("Content-Security-Policy", csp)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?", 1)[0].lstrip("/")
            if log is not None:
                log.append(path)
            if path == "__outer.html":
                if srcdoc:
                    body = (root / page).read_text(encoding="utf-8")
                    if wrap:
                        body = SKELETON_PRE + body + SKELETON_SUF
                    body = body.replace("<head>", '<head><base href="http://%s/">' % self.headers.get("Host"), 1) if "<head>" in body else '<base href="http://%s/">' % self.headers.get("Host") + body
                    inner = 'srcdoc="%s"' % _html.escape(body, quote=True)
                else:
                    inner = 'src="/%s"' % page
                sb = ('sandbox="%s"' % sandbox) if sandbox is not None else ""
                outer = '<!doctype html><html><head><meta name=viewport content="width=device-width,initial-scale=1"></head><body style="margin:0"><iframe id="app" %s %s style="border:0;width:100vw;height:100vh;display:block"></iframe></body></html>' % (sb, inner)
                return self._send(200, outer.encode(), "text/html; charset=utf-8")
            if any(path.startswith(h) for h in hide):
                return self._send(404, b"not found", "text/plain")
            f = root / path
            if not f.is_file():
                return self._send(404, b"not found", "text/plain")
            data = f.read_bytes()
            ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
            if path.endswith(".js"):
                ctype = "application/javascript"
            if path.endswith(".json"):
                ctype = "application/json"
            if path.endswith(".txt"):
                ctype = "text/plain"
            if path.endswith(".html"):
                ctype = "text/html; charset=utf-8"
                if wrap:
                    data = SKELETON_PRE.encode() + data + SKELETON_SUF.encode()
            if mime == "plain" and not path.endswith(".html"):          # the page itself must stay HTML or nothing runs at all
                ctype = "text/plain"
            return self._send(200, data, ctype)

        do_HEAD = do_GET

    return H


def serve(root, **opts):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), make_handler(Path(root), **opts))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port
