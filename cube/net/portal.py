"""Captive Wi-Fi setup page (aiohttp) — GalaxySMP look, mobile-first.

Shown while the Cube is a hotspot. Phones open http://10.42.0.1/
(or http://127.0.0.1:8765/ in the desktop simulator).
"""

from __future__ import annotations

import asyncio
import html
import logging
from typing import Awaitable, Callable, Optional

from aiohttp import web

from cube.net.wifi import HOTSPOT_GATEWAY, HOTSPOT_PASSWORD, WifiManager

log = logging.getLogger("cube.portal")

ConnectHandler = Callable[[str, str], Awaitable[None]]


SETUP_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Galaxy Cube · Wi-Fi setup</title>
<meta name="theme-color" content="#0a0c1b">
<style>
:root {
  color-scheme: dark;
  --bg: #0a0c1b;
  --bg-raised: #10132a;
  --surface: #151933;
  --surface-2: #1b2040;
  --border: #252b4d;
  --text: #e9ebf8;
  --text-2: #b4b8d6;
  --text-3: #8186ad;
  --accent: #2457eb;
  --accent-hover: #3567f2;
  --ok: #34c77b;
  --bad: #f0566f;
  --grad: linear-gradient(90deg, #4FEBFD, #3DAAF4 40%, #8A5CFF 85%);
  --radius: 12px;
  --font: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
* { box-sizing: border-box; }
html, body { margin: 0; min-height: 100%; }
body {
  font-family: var(--font);
  color: var(--text);
  background:
    radial-gradient(900px 500px at 90% -10%, rgba(61,170,244,.18), transparent 55%),
    radial-gradient(700px 480px at -15% 30%, rgba(138,92,255,.16), transparent 55%),
    radial-gradient(800px 600px at 50% 120%, rgba(33,73,221,.18), transparent 55%),
    var(--bg);
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  padding: 28px 18px 48px;
}
.wrap { max-width: 420px; margin: 0 auto; }
.brand {
  font-weight: 800; letter-spacing: -0.03em; font-size: 1.55rem;
  background: var(--grad); -webkit-background-clip: text; background-clip: text;
  color: transparent; margin: 0 0 6px;
}
.sub { color: var(--text-2); margin: 0 0 22px; font-size: .98rem; }
.card {
  background: rgba(21, 25, 51, .92);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px 16px 16px;
  backdrop-filter: blur(8px);
}
label { display: block; font-size: .82rem; color: var(--text-3); margin: 0 0 6px; font-weight: 600; }
select, input[type=password], input[type=text] {
  width: 100%; appearance: none; border-radius: 10px;
  border: 1px solid var(--border); background: var(--surface-2); color: var(--text);
  padding: 12px 14px; font-size: 1rem; margin-bottom: 14px;
}
select {
  background-image: linear-gradient(45deg, transparent 50%, var(--text-3) 50%),
                    linear-gradient(135deg, var(--text-3) 50%, transparent 50%);
  background-position: calc(100% - 18px) 50%, calc(100% - 13px) 50%;
  background-size: 5px 5px, 5px 5px; background-repeat: no-repeat; padding-right: 34px;
}
.row { display: flex; gap: 10px; align-items: center; margin-bottom: 8px; }
.sig {
  flex: none; width: 42px; text-align: right; font-size: .75rem; color: var(--text-3);
  font-variant-numeric: tabular-nums;
}
.btn {
  display: inline-flex; align-items: center; justify-content: center; width: 100%;
  border: 0; border-radius: 10px; padding: 13px 16px; font-weight: 700; font-size: 1rem;
  cursor: pointer; background: var(--accent); color: #fff; margin-top: 4px;
}
.btn:hover { background: var(--accent-hover); }
.btn:disabled { opacity: .55; cursor: wait; }
.hint { color: var(--text-3); font-size: .85rem; margin: 14px 0 0; }
.msg { margin: 0 0 14px; padding: 10px 12px; border-radius: 8px; font-size: .92rem; }
.msg.err { background: rgba(240,86,111,.15); color: #ffb3bf; border: 1px solid rgba(240,86,111,.35); }
.msg.ok { background: rgba(52,199,123,.12); color: #9af0c0; border: 1px solid rgba(52,199,123,.35); }
.msg.info { background: rgba(36,87,235,.15); color: #b7c8ff; border: 1px solid rgba(36,87,235,.35); }
.meta { margin-top: 18px; color: var(--text-3); font-size: .8rem; }
code { font-family: ui-monospace, Menlo, Consolas, monospace; color: #6fd3fb; }
</style>
</head>
<body>
  <div class="wrap">
    <h1 class="brand">Galaxy Cube</h1>
    <p class="sub">Pick your home Wi-Fi so this Cube can reach GalaxySMP.</p>
    <div class="card">
      __MESSAGE__
      <form method="POST" action="/connect" id="f">
        <label for="ssid">Wi-Fi network</label>
        <select id="ssid" name="ssid" required>
          __OPTIONS__
        </select>
        <label for="password">Password</label>
        <input id="password" name="password" type="password" autocomplete="current-password"
               placeholder="Leave blank if open">
        <button class="btn" type="submit" id="go">Connect Cube</button>
      </form>
      <p class="hint">You joined hotspot <code>__HOTSPOT__</code>
        (password <code>__HOTSPOT_PW__</code>). After this, the Cube leaves the hotspot
        and joins your network.</p>
    </div>
    <p class="meta">galaxymc.us · device <code>__DEVICE__</code></p>
  </div>
  <script>
    document.getElementById('f').addEventListener('submit', function () {
      var b = document.getElementById('go');
      b.disabled = true; b.textContent = 'Connecting…';
    });
  </script>
</body>
</html>
"""

CONNECTING_HTML = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Connecting…</title>
<meta http-equiv="refresh" content="8;url=/done">
<style>
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
font-family:system-ui,sans-serif;background:#0a0c1b;color:#e9ebf8;text-align:center;padding:24px}
h1{font-size:1.4rem;background:linear-gradient(90deg,#4FEBFD,#3DAAF4 40%,#8A5CFF);
-webkit-background-clip:text;background-clip:text;color:transparent}
p{color:#b4b8d6;max-width:28em}
</style></head>
<body><div>
<h1>Connecting to __SSID__…</h1>
<p>The Cube is joining your Wi-Fi. You can leave this hotspot now —
your phone will switch back to home Wi-Fi on its own.</p>
</div></body></html>
"""

DONE_HTML = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Connected</title>
<style>
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
font-family:system-ui,sans-serif;background:#0a0c1b;color:#e9ebf8;text-align:center;padding:24px}
h1{color:#34c77b} p{color:#b4b8d6}
</style></head>
<body><div>
<h1>You're set</h1>
<p>Galaxy Cube is on your Wi-Fi. Look at the Cube screen for the next step
(pairing code at cube.galaxymc.us).</p>
</div></body></html>
"""


class SetupPortal:
    """Tiny captive portal. Call start()/stop(); wait on `.done`."""

    def __init__(
        self,
        wifi: WifiManager,
        device_id: str,
        on_connect: Optional[ConnectHandler] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> None:
        self.wifi = wifi
        self.device_id = device_id
        self.on_connect = on_connect
        self.done = asyncio.Event()
        self.last_error: Optional[str] = None
        self.connecting_ssid: Optional[str] = None
        if wifi.simulator:
            self.host = host or "127.0.0.1"
            self.port = port or 8765
        else:
            self.host = host or "0.0.0.0"
            self.port = port or 80
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None

    @property
    def url(self) -> str:
        shown_host = HOTSPOT_GATEWAY if not self.wifi.simulator else self.host
        if self.port in (80,):
            return f"http://{shown_host}/"
        return f"http://{shown_host}:{self.port}/"

    async def start(self) -> str:
        app = web.Application()
        app.router.add_get("/", self._index)
        app.router.add_get("/index.html", self._index)
        app.router.add_post("/connect", self._connect)
        app.router.add_get("/done", self._done)
        app.router.add_get("/api/networks", self._api_networks)
        # Captive portal detection endpoints → redirect to setup
        for path in (
            "/generate_204",
            "/gen_204",
            "/hotspot-detect.html",
            "/library/test/success.html",
            "/connecttest.txt",
            "/ncsi.txt",
            "/canonical.html",
            "/success.txt",
            "/redirect",
        ):
            app.router.add_route("*", path, self._captive_probe)
        app.router.add_route("*", "/{tail:.*}", self._captive_probe)

        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
        log.info("Setup portal listening on %s", self.url)
        return self.url

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            self._site = None

    async def _index(self, request: web.Request) -> web.Response:
        networks = self.wifi.list_networks()
        if not networks:
            options = '<option value="">(no networks found — refresh)</option>'
        else:
            parts = []
            for n in networks:
                ssid = n["ssid"]
                sig = int(n.get("signal") or 0)
                sec = n.get("security") or "Open"
                label = f"{ssid}  ·  {sig}%  ·  {sec or 'Open'}"
                parts.append(
                    f'<option value="{html.escape(ssid, quote=True)}">'
                    f"{html.escape(label)}</option>"
                )
            options = "\n".join(parts)

        if self.last_error:
            msg = f'<p class="msg err">{html.escape(self.last_error)}</p>'
        elif self.connecting_ssid:
            msg = f'<p class="msg info">Connecting to <strong>{html.escape(self.connecting_ssid)}</strong>…</p>'
        else:
            msg = ""

        page = (
            SETUP_HTML.replace("__OPTIONS__", options)
            .replace("__MESSAGE__", msg)
            .replace("__HOTSPOT__", html.escape(self.wifi.hotspot_ssid or self.device_id))
            .replace("__HOTSPOT_PW__", html.escape(HOTSPOT_PASSWORD))
            .replace("__DEVICE__", html.escape(self.device_id))
        )
        return web.Response(text=page, content_type="text/html")

    async def _connect(self, request: web.Request) -> web.Response:
        data = await request.post()
        ssid = str(data.get("ssid") or "").strip()
        password = str(data.get("password") or "")
        if not ssid:
            self.last_error = "Pick a Wi-Fi network."
            raise web.HTTPFound("/")

        self.last_error = None
        self.connecting_ssid = ssid
        # Respond first so the phone sees "Connecting…", then join Wi-Fi.
        page = CONNECTING_HTML.replace("__SSID__", html.escape(ssid))
        asyncio.create_task(self._do_connect(ssid, password))
        return web.Response(text=page, content_type="text/html")

    async def _do_connect(self, ssid: str, password: str) -> None:
        try:
            if self.on_connect:
                await self.on_connect(ssid, password)
            else:
                await asyncio.to_thread(self.wifi.connect, ssid, password)
            self.done.set()
        except Exception as exc:
            log.exception("Wi-Fi connect failed")
            self.last_error = str(exc) or "Could not join that network."
            self.connecting_ssid = None
            # Hotspot may have been torn down — try to bring it back for another attempt.
            try:
                if not self.wifi.hotspot_active:
                    await asyncio.to_thread(self.wifi.start_hotspot, self.device_id)
            except Exception:
                log.exception("Failed to restart hotspot after connect error")

    async def _done(self, request: web.Request) -> web.Response:
        return web.Response(text=DONE_HTML, content_type="text/html")

    async def _api_networks(self, request: web.Request) -> web.Response:
        return web.json_response({"ok": True, "networks": self.wifi.list_networks()})

    async def _captive_probe(self, request: web.Request) -> web.Response:
        raise web.HTTPFound("/")
