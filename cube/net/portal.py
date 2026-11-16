"""The setup page phones see on the CUBE-XXXX hotspot (spec §6). It only saves Wi-Fi."""
import asyncio
import html

from aiohttp import web

from .. import config

log = config.log

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Galaxy Cube setup</title>
<style>
:root{{--bg:#0b1026;--card:#121936;--line:#222c57;--text:#e8ecff;--muted:#97a0c6;--cyan:#22d3ee;--blue:#3b82f6;--purple:#8b5cf6;--bad:#ffb4c8}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}}
.brand{{height:4px;background:linear-gradient(90deg,var(--cyan),var(--blue),var(--purple))}}
.wrap{{max-width:440px;margin:0 auto;padding:22px 18px 40px}}
.mark{{display:flex;align-items:center;gap:10px;font-weight:700;letter-spacing:.14em;font-size:13px;color:var(--muted)}}
.mark i{{width:14px;height:14px;border:2px solid var(--cyan);border-radius:3px;display:block}}
h1{{font-size:24px;margin:18px 0 6px;font-weight:650}}
p{{color:var(--muted);margin:0 0 18px}}
fieldset{{border:1px solid var(--line);border-radius:10px;padding:0;margin:0 0 14px;background:var(--card)}}
legend{{padding:0 6px;margin-left:10px;color:var(--muted);font-size:13px}}
label.net{{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:13px 14px;border-top:1px solid var(--line);cursor:pointer}}
label.net:first-of-type{{border-top:0}}
label.net input{{accent-color:var(--cyan);margin:0 10px 0 0;width:18px;height:18px}}
.name{{display:flex;align-items:center;min-width:0;overflow-wrap:anywhere}}
.sig{{color:var(--muted);font-size:13px;white-space:nowrap;display:flex;gap:6px;align-items:center}}
.bars{{display:inline-flex;gap:2px;align-items:flex-end;height:12px}}.bars b{{width:3px;background:var(--line);border-radius:1px}}.bars b.on{{background:var(--cyan)}}
.field{{padding:12px 14px}}.field+.field{{border-top:1px solid var(--line)}}
.field label{{display:block;font-size:13px;color:var(--muted);margin-bottom:6px}}
input[type=password],input[type=text]{{width:100%;padding:12px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--text);font-size:16px}}
input:focus,button:focus{{outline:2px solid var(--cyan);outline-offset:2px}}
button{{width:100%;padding:14px;border:0;border-radius:10px;background:var(--cyan);color:#06202a;font-size:17px;font-weight:650}}
.err{{border:1px solid #6b2442;background:#2a1026;color:var(--bad);padding:12px;border-radius:8px;margin-bottom:14px}}
.small{{font-size:14px;margin-top:14px}}
</style></head><body><div class="brand"></div><div class="wrap">
<div class="mark"><i></i>GALAXY CUBE</div>{body}</div></body></html>"""

LOCK = ('<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" '
        'aria-label="Password"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>')


def _bars(signal):
    on = 1 + min(3, signal // 25)
    return '<span class="bars">' + "".join(
        f'<b class="{"on" if i < on else ""}" style="height:{3 + i * 3}px"></b>' for i in range(4)) + "</span>"


def _network_form(networks, error):
    rows = "".join(
        f'<label class="net"><span class="name"><input type="radio" name="ssid" value="{html.escape(n["ssid"])}"'
        f'{" checked" if i == 0 else ""}>{html.escape(n["ssid"])}</span>'
        f'<span class="sig">{LOCK if n["secure"] else ""}{_bars(n["signal"])}</span></label>'
        for i, n in enumerate(networks))
    if not rows:
        rows = '<div class="field">No networks found. Type the name below.</div>'
    err = f'<div class="err">{html.escape(error)}</div>' if error else ""
    return (f'<h1>Connect to Wi-Fi</h1><p>Pick your home Wi-Fi. Your console has to be on the same one.</p>{err}'
            f'<form method="post" action="/connect"><fieldset><legend>Networks nearby</legend>{rows}</fieldset>'
            '<fieldset><div class="field"><label for="other">Not listed? Type its name</label>'
            '<input type="text" id="other" name="other" autocomplete="off" placeholder="Wi-Fi name"></div>'
            '<div class="field"><label for="password">Password</label>'
            '<input type="password" id="password" name="password" placeholder="Wi-Fi password"></div></fieldset>'
            '<button type="submit">Connect</button></form>'
            '<p class="small">This page only saves Wi-Fi. You link your account later with a code.</p>')


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
        body = ('<h1>Connecting…</h1><p>Look at the Cube\'s screen. If it says the password was wrong, '
                'join the CUBE Wi-Fi again and this page comes back.</p>')
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
