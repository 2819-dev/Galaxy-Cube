"""A pretend galaxymc.us for testing the Cube on a computer (only the /api/cube endpoints the Cube uses).

  python3 dev/mock_site.py                 # runs on http://localhost:8099
  CUBE_FAKE=1 CUBE_API=http://localhost:8099 python3 -m cube.main

Then "link" the Cube by opening http://localhost:8099/dev/link (links the newest code),
and test unlinking with http://localhost:8099/dev/unlink.

Voice: another player "Mia" stands 5 blocks away and plays a tone. http://localhost:8099/dev/voice shows
what the pretend voice server got from the Cube (mic audio, talking, mute).
"""
import asyncio
import fractions
import json
import random
import secrets
import string

from aiohttp import web

try:  # voice needs aiortc (pip install aiortc); everything else works without it
    import av
    import numpy as np
    from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
except ImportError:
    av = None

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
        "voice": {"url": f"ws://{request.host}/api/cube/voice"}})


async def dev_link(request):
    if not pairings:
        return web.Response(text="No code waiting")
    p = list(pairings.values())[-1]
    p["linked"] = True
    return web.Response(text=f"Linked {p['code']}")


async def dev_unlink(request):
    tokens.clear()
    return web.Response(text="Unlinked every Cube")


# ---------------- voice (same messages as the real voice server) ----------------

ME, MIA = 14, 21
voice_stats = {"connected": False, "mic_frames": 0, "loud_frames": 0, "talking": False, "mic": None,
               "deafened": None, "group": None, "pulled": [], "closed": []}
GROUPS = [{"id": "g1", "name": "Builders", "locked": False, "members": []},
          {"id": "g2", "name": "Secret base", "locked": True, "members": []}]


if av:
    class Tone(MediaStreamTrack):
        """Mia's voice: a quiet 440 Hz tone, in real time."""
        kind = "audio"

        def __init__(self):
            super().__init__()
            self.pts = 0
            self.start = None

        async def recv(self):
            loop = asyncio.get_running_loop()
            if self.start is None:
                self.start = loop.time()
            wait = self.start + self.pts / 48000 - loop.time()
            if wait > 0:
                await asyncio.sleep(wait)
            t = (np.arange(960) + self.pts) / 48000
            pcm = (np.sin(2 * np.pi * 440 * t) * 6000).astype(np.int16)
            frame = av.AudioFrame.from_ndarray(pcm.reshape(1, -1), format="s16", layout="mono")
            frame.sample_rate, frame.pts, frame.time_base = 48000, self.pts, fractions.Fraction(1, 48000)
            self.pts += 960
            return frame


async def count_mic(track):
    while True:
        try:
            frame = await track.recv()
        except Exception:
            return
        voice_stats["mic_frames"] += 1
        if np.abs(frame.to_ndarray()).max() > 500:
            voice_stats["loud_frames"] += 1


async def voice(request):
    auth = request.headers.get("Authorization", "")
    if auth.removeprefix("Bearer ") not in tokens:
        return error(401, "This Cube isn't linked. Pair it again.")
    if not av:
        return error(503, "Voice chat isn't set up yet.")
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    pc = None
    me = {"id": ME, "username": "Steve", "inGame": True, "dim": "Overworld", "group": None, "mic": False,
          "deafened": False, "talking": False, "voiceMuted": False, "global": False, "canGlobal": True,
          "published": False}
    mia = {"id": MIA, "username": "Mia", "inGame": True, "dim": "Overworld", "group": None, "mic": True,
           "deafened": False, "talking": True, "voiceMuted": False, "global": False, "canGlobal": False,
           "published": True}
    voice_stats.update(connected=True, mic_frames=0, loud_frames=0)

    async def roster():
        await ws.send_json({"type": "roster", "users": [me, mia], "groups": GROUPS})

    async def positions():
        while True:
            await ws.send_json({"type": "pos", "list": [[ME, 0, 64, 0, 0, "Overworld"], [MIA, 5, 64, 0, 90, "Overworld"]]})
            await asyncio.sleep(0.5)

    await ws.send_json({"type": "hello", "you": ME, "range": 48, "voiceMutedUntil": None})
    await roster()
    pos_task = asyncio.create_task(positions())
    try:
        async for msg in ws:
            if msg.data == "ping":
                await ws.send_str("pong")
                continue
            m = json.loads(msg.data)
            kind, req = m.get("type"), m.get("req")

            async def reply(**data):
                await ws.send_json({"type": "reply", "req": req, **data})

            if kind == "state":
                for k in ("mic", "deafened", "talking"):
                    if k in m:
                        me[k] = m[k]
                        voice_stats[k] = m[k]
                if list(m) == ["type", "talking"]:
                    await ws.send_json({"type": "talk", "id": ME, "on": m["talking"]})
                else:
                    await roster()
            elif kind == "rtc.session":
                pc = RTCPeerConnection()
                pc.on("track", lambda t: asyncio.ensure_future(count_mic(t)))
                await reply(ok=True)
            elif kind == "rtc.push":
                await pc.setRemoteDescription(RTCSessionDescription(m["sdp"], "offer"))
                await pc.setLocalDescription(await pc.createAnswer())
                me["published"] = True
                await roster()
                await reply(ok=True, answer={"type": "answer", "sdp": pc.localDescription.sdp})
            elif kind == "rtc.pull":
                owners = [o for o in m.get("owners", []) if o == MIA]
                if not owners:
                    await reply(ok=True, tracks=[])
                    continue
                tx = pc.addTransceiver(Tone(), direction="sendonly")
                await pc.setLocalDescription(await pc.createOffer())
                voice_stats["pulled"].append(MIA)
                await reply(ok=True, tracks=[{"mid": tx.mid, "owner": MIA}],
                            offer={"type": "offer", "sdp": pc.localDescription.sdp})
            elif kind == "rtc.renegotiate":
                await pc.setRemoteDescription(RTCSessionDescription(m["sdp"], "answer"))
                await reply(ok=True)
            elif kind == "rtc.close":
                voice_stats["closed"] += m.get("mids", [])
                await pc.setRemoteDescription(RTCSessionDescription(m["sdp"], "offer"))
                await pc.setLocalDescription(await pc.createAnswer())
                await reply(ok=True, answer={"type": "answer", "sdp": pc.localDescription.sdp})
            elif kind == "group.join":
                g = next((g for g in GROUPS if g["id"] == m.get("id")), None)
                if not g:
                    await reply(error="That group no longer exists.")
                elif g["locked"]:
                    await reply(error="Wrong group password.")
                else:
                    me["group"] = voice_stats["group"] = g["id"]
                    await roster()
                    await reply(ok=True)
            elif kind == "group.leave":
                me["group"] = voice_stats["group"] = None
                await roster()
                await reply(ok=True)
            elif kind == "global":
                me["global"] = bool(m.get("on"))
                await roster()
                await reply(ok=True)
    finally:
        pos_task.cancel()
        voice_stats["connected"] = False
        if pc:
            await pc.close()
    return ws


async def dev_voice(request):
    return web.json_response(voice_stats)


app = web.Application()
app.router.add_post("/api/cube/pair/start", pair_start)
app.router.add_post("/api/cube/pair/poll", pair_poll)
app.router.add_get("/api/cube/me", me)
app.router.add_get("/api/cube/voice", voice)
app.router.add_get("/dev/voice", dev_voice)
app.router.add_get("/dev/link", dev_link)
app.router.add_get("/dev/unlink", dev_unlink)

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    web.run_app(app, port=8099)
