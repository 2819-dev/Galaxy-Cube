"""A pretend galaxymc.us for testing the Cube on a computer (only the /api/cube endpoints the Cube uses).

  python3 dev/mock_site.py                 # runs on http://localhost:8099
  CUBE_FAKE=1 CUBE_API=http://localhost:8099 python3 -m cube.main

Then "link" the Cube by opening http://localhost:8099/dev/link (links the newest code),
and test unlinking with http://localhost:8099/dev/unlink.
"""
import random
import secrets
import string

from aiohttp import web

pairings = {}   # pollToken -> {"code", "linked"}
tokens = set()


def error(status, message):
    return web.json_response({"ok": False, "error": message}, status=status)


async def pair_start(request):
    body = await request.json()
    if not str(body.get("deviceId", "")).startswith("CUBE-"):
        return error(400, "Bad device id")
    letters = string.ascii_uppercase + string.digits
    code = "".join(random.choices(letters, k=3)) + "-" + "".join(random.choices(letters, k=3))
    poll = secrets.token_hex(8)
    pairings[poll] = {"code": code, "linked": False}
    print("New pairing code", code)
    return web.json_response({"ok": True, "code": code, "pollToken": poll, "expiresAt": 0,
                              "url": "galaxymc.us/cube"})


async def pair_poll(request):
    body = await request.json()
    p = pairings.get(body.get("pollToken"))
    if not p:
        return error(404, "Unknown pairing.")
    if not p["linked"]:
        return web.json_response({"ok": True, "status": "waiting"})
    token = secrets.token_hex(16)
    tokens.add(token)
    del pairings[body["pollToken"]]
    return web.json_response({"ok": True, "status": "linked", "deviceToken": token, "username": "Steve"})


async def me(request):
    auth = request.headers.get("Authorization", "")
    if auth.removeprefix("Bearer ") not in tokens:
        return error(401, "This Cube isn't linked. Pair it again.")
    return web.json_response({
        "ok": True,
        "device": {"id": 1, "deviceId": "CUBE-F00D", "name": "Living room", "model": "cube"},
        "user": {"id": 14, "username": "Steve", "gamertag": "Steve"},
        "server": {"name": "GalaxySMP", "motd": "GalaxySMP", "host": "galaxymc.smp.live", "port": 9030},
        "voice": {"url": "wss://galaxymc.us/api/cube/voice"}})


async def dev_link(request):
    if not pairings:
        return web.Response(text="No code waiting")
    p = list(pairings.values())[-1]
    p["linked"] = True
    return web.Response(text=f"Linked {p['code']}")


async def dev_unlink(request):
    tokens.clear()
    return web.Response(text="Unlinked every Cube")


app = web.Application()
app.router.add_post("/api/cube/pair/start", pair_start)
app.router.add_post("/api/cube/pair/poll", pair_poll)
app.router.add_get("/api/cube/me", me)
app.router.add_get("/dev/link", dev_link)
app.router.add_get("/dev/unlink", dev_unlink)

if __name__ == "__main__":
    web.run_app(app, port=8099)
