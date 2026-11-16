"""The setup page phones see on the CUBE-XXXX hotspot (spec §6). It only saves Wi-Fi."""
import asyncio
import html

from aiohttp import web

from .. import config

log = config.log

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Galaxy Cube setup</title>
<style>
:root{{--bg:#0b1026;--card:#141b3d;--text:#e8ecff;--muted:#9aa3c7;--grad:linear-gradient(90deg,#22d3ee,#3b82f6,#8b5cf6)}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:16px system-ui,sans-serif;padding:20px}}
.wrap{{max-width:420px;margin:0 auto}}h1{{font-size:26px;margin:8px 0 4px;background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}}
p{{color:var(--muted);margin:0 0 18px}}.card{{background:var(--card);border-radius:12px;padding:16px;margin-bottom:14px}}
label{{display:flex;justify-content:space-between;align-items:center;padding:12px 4px;border-bottom:1px solid #222b55;cursor:pointer}}
label:last-child{{border:0}}input[type=radio]{{margin-right:10px}}.sig{{color:var(--muted);font-size:13px}}
input[type=password],input[type=text]{{width:100%;padding:12px;border-radius:8px;border:1px solid #2a3570;background:#0b1026;color:var(--text);font-size:16px;margin-top:8px}}
button{{width:100%;padding:14px;border:0;border-radius:10px;background:var(--grad);color:#fff;font-size:17px;font-weight:600;margin-top:6px}}
.err{{background:#3b1530;color:#ffb4c8;padding:12px;border-radius:8px;margin-bottom:14px}}a{{color:#7dd3fc}}
</style></head><body><div class="wrap">
<h1>Galaxy Cube</h1><p>Pick your home Wi-Fi. Your console must use the same Wi-Fi.</p>{body}</div></body></html>"""


def _network_form(networks, error):
    rows = "".join(
        f'<label><span><input type="radio" name="ssid" value="{html.escape(n["ssid"])}"{" checked" if i == 0 else ""}>'
        f'{html.escape(n["ssid"])}</span><span class="sig">{"🔒 " if n["secure"] else ""}{n["signal"]}%</span></label>'
        for i, n in enumerate(networks))
    if not rows:
        rows = "<p>No networks found. Type the name below.</p>"
    err = f'<div class="err">{html.escape(error)}</div>' if error else ""
    return (f'{err}<form method="post" action="/connect"><div class="card">{rows}</div>'
            '<div class="card">Other network (optional)<input type="text" name="other" placeholder="Wi-Fi name">'
            '<br><br>Password<input type="password" name="password" placeholder="Wi-Fi password"></div>'
            '<button type="submit">Connect</button></form>'
            '<p style="margin-top:14px">Don\'t see your Wi-Fi? Type its name under "Other network".</p>')


class Portal:
    """Runs the setup page until the phone sends a network. Then `chosen` holds (ssid, password)."""

    def __init__(self, networks, error=""):
        self.networks = networks
        self.error = error
        self.chosen = asyncio.get_running_loop().create_future()
        self.runner = None

    async def page(self, request):
        return web.Response(text=PAGE.format(body=_network_form(self.networks, self.error)),
                            content_type="text/html")

    async def submit(self, request):
        form = await request.post()
        ssid = (form.get("other") or "").strip() or (form.get("ssid") or "").strip()
        if not ssid:
            self.error = "Pick a Wi-Fi network first."
            raise web.HTTPFound("/")
        if not self.chosen.done():
            self.chosen.set_result((ssid, form.get("password") or ""))
        body = ('<div class="card"><b>Connecting…</b><br><br>Look at the Cube\'s screen. '
                'If it says the password was wrong, join the CUBE Wi-Fi again and this page will come back.</div>')
        return web.Response(text=PAGE.format(body=body), content_type="text/html")

    async def anything_else(self, request):
        # Phones check random addresses to find captive portals; send them all to the setup page.
        raise web.HTTPFound("http://10.42.0.1/" if not config.FAKE else "/")

    async def start(self):
        app = web.Application()
        app.router.add_get("/", self.page)
        app.router.add_post("/connect", self.submit)
        app.router.add_route("*", "/{tail:.*}", self.anything_else)
        self.runner = web.AppRunner(app, access_log=None)
        await self.runner.setup()
        port = 8080 if config.FAKE else 80
        await web.TCPSite(self.runner, "0.0.0.0", port).start()
        log.info("Setup page running on port %s", port)

    async def stop(self):
        if self.runner:
            await self.runner.cleanup()
