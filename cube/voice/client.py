"""Voice chat (spec §8): the same protocol as the website's voice page (public/js/voice.js).

The Cube connects to wss://galaxymc.us/api/cube/voice with its device token, sends the mic to the voice
relay over WebRTC, and receives only the people it's allowed to hear (nearby in game, same group,
Global Mic). The server double-checks everything; the Cube just asks.
"""
import asyncio
import fractions
import json
import math
import os
import time

import aiohttp
import av
import numpy as np
from aiortc import (MediaStreamTrack, RTCBundlePolicy, RTCConfiguration, RTCIceServer, RTCPeerConnection,
                    RTCSessionDescription)

from .. import config
from .audio import FRAME, RATE, Audio

log = config.log
FULL_VOLUME_WITHIN = 4    # blocks
FADE_POWER = 2.6
TALK_LEVEL = 0.02         # open mic: louder than this counts as talking
STUN = os.environ.get("CUBE_STUN", "stun:stun.cloudflare.com:3478")  # empty = none (only for local tests)


class VoiceError(Exception):
    """A message from the voice server that's safe to show on the screen."""


def distance_gain(d, rng):
    """How loud (0..1) someone d blocks away sounds. Same curve as the website."""
    if d <= FULL_VOLUME_WITHIN:
        return 1.0
    t = min(1.0, (d - FULL_VOLUME_WITHIN) / max(1, rng - FULL_VOLUME_WITHIN))
    return (1 - t) ** FADE_POWER


class MicTrack(MediaStreamTrack):
    """Our microphone as a WebRTC track. Sends silence when we shouldn't be heard (push-to-talk not held,
    muted, deafened)."""
    kind = "audio"

    def __init__(self, voice):
        super().__init__()
        self.voice = voice
        self.pts = 0

    async def recv(self):
        pcm = await self.voice.audio.mic.get()
        if not self.voice.transmitting():
            pcm = np.zeros(FRAME, np.int16)
        frame = av.AudioFrame.from_ndarray(pcm.reshape(1, -1), format="s16", layout="mono")
        frame.sample_rate = RATE
        frame.pts = self.pts
        frame.time_base = fractions.Fraction(1, RATE)
        self.pts += len(pcm)
        return frame


class Voice:
    def __init__(self, settings, on_change):
        self.settings = settings          # the App's settings dict: voice_mode, voice_audio, voice_volume
        self.on_change = on_change        # called whenever the screen should be redrawn
        self.audio = Audio()
        self.task = None
        self.reset()

    def reset(self):
        self.ws = None
        self.pc = None
        self.connected = False
        self.status = "off"               # off / connecting / on / a message
        self.my_id = None
        self.range = 48
        self.users = {}
        self.groups = []
        self.pos = {}
        self.subs = {}                    # owner id -> mid
        self.readers = {}                 # owner id -> task reading their audio
        self.mid_owner = {}
        self.pending = {}
        self.req = 0
        self.talking = False
        self.talk_until = 0
        self.voice_muted_until = None
        self.closed_reason = None
        self.sync_needed = asyncio.Event()
        self.rtc_lock = asyncio.Lock()

    # ---------- what the menu and buttons use ----------

    @property
    def joined(self):
        return self.task is not None and not self.task.done()

    @property
    def mic_on(self):
        return self.settings.setdefault("voice_mic", True)

    @property
    def deafened(self):
        return self.settings.setdefault("voice_deafened", False)

    @property
    def ptt(self):
        return self.settings.get("voice_mode", "Push-to-talk") == "Push-to-talk"

    talk_held = False

    def voice_muted(self):
        return bool(self.voice_muted_until)

    def transmitting(self):
        return (self.connected and self.mic_on and not self.deafened and not self.voice_muted()
                and (not self.ptt or self.talk_held))

    def me(self):
        return self.users.get(self.my_id) or {}

    def my_group(self):
        gid = self.me().get("group")
        return next((g for g in self.groups if g["id"] == gid), None)

    def join(self, url, token):
        if self.joined:
            return
        self.reset()
        self.status = "connecting"
        self.task = asyncio.create_task(self._run(url, token))

    async def leave(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except (asyncio.CancelledError, Exception):
                pass
        self.task = None
        self.status = "off"
        self.on_change()

    def button(self, event):
        """TALK / MUTE from the Cube's buttons."""
        if event in ("talk_down", "talk_up"):
            self.talk_held = event == "talk_down"
        elif event == "mute":
            self.settings["voice_mic"] = not self.mic_on
            self._send_state(mic=self.mic_on)
        elif event == "mute_long":
            self.settings["voice_deafened"] = not self.deafened
            self._send_state(deafened=self.deafened)
            self._update_mix()
        self._check_talking()
        self.on_change()

    def set_volume(self, percent):
        self.settings["voice_volume"] = percent
        self.audio.volume = percent / 100

    async def join_group(self, gid):
        await self.request("group.join", id=gid)

    async def leave_group(self):
        await self.request("group.leave")

    async def set_global(self, on):
        await self.request("global", on=on)

    # ---------- connection ----------

    async def _run(self, url, token):
        wait = 1
        try:
            while True:
                try:
                    await self._session(url, token)
                    log.info("Voice connection closed by the server")
                    wait = 1
                except VoiceError as e:
                    self.status = str(e)
                    log.warning("Voice: %s", e)
                    if getattr(e, "final", False):
                        return
                except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError) as e:
                    self.status = "No connection"
                    log.warning("Voice connection lost: %s", e.__class__.__name__)
                except Exception:
                    self.status = "Voice problem"
                    log.exception("Voice problem")
                finally:
                    await self._cleanup()
                if self.closed_reason:          # staff removed us, or we joined somewhere else: don't retry
                    self.status = self.closed_reason
                    return
                self.on_change()
                await asyncio.sleep(wait)
                wait = min(wait * 2, 30)
                self.status = "connecting"
                self.on_change()
        finally:
            self.on_change()

    async def _session(self, url, token):
        headers = {"Authorization": f"Bearer {token}", "X-Cube-Firmware": config.VERSION}
        async with aiohttp.ClientSession() as http:
            try:
                ws = await http.ws_connect(url, headers=headers, timeout=aiohttp.ClientWSTimeout(ws_close=5))
            except aiohttp.WSServerHandshakeError as e:
                err = VoiceError({401: "Cube not linked", 403: "Link Minecraft first",
                                  503: "Voice is offline"}.get(e.status, f"Voice error {e.status}"))
                err.final = e.status in (401, 403)
                raise err
            self.ws = ws
            hello = asyncio.get_running_loop().create_future()
            reader = asyncio.create_task(self._read(ws, hello))
            workers = []
            try:
                await asyncio.wait_for(asyncio.shield(hello), 15)
                self.audio.volume = self.settings.get("voice_volume", 80) / 100
                self.audio.start(self.settings.get("voice_audio", "Auto"))
                await self._setup_rtc()
                self._send_state(mic=self.mic_on, deafened=self.deafened, talking=False)
                self.connected = True
                self.status = "on"
                self.on_change()
                log.info("Voice connected")
                workers = [asyncio.create_task(self._sync_loop()), asyncio.create_task(self._talk_loop()),
                           asyncio.create_task(self._ping_loop(ws))]
                await reader
            finally:
                for t in workers + [reader]:
                    t.cancel()

    async def _read(self, ws, hello):
        async for msg in ws:
            if msg.type != aiohttp.WSMsgType.TEXT or msg.data == "pong":
                continue
            try:
                m = json.loads(msg.data)
            except ValueError:
                continue
            kind = m.get("type")
            if kind == "hello":
                self.my_id = m.get("you")
                self.range = m.get("range") or 48
                self.voice_muted_until = m.get("voiceMutedUntil")
                if not hello.done():
                    hello.set_result(True)
            elif kind == "reply":
                fut = self.pending.pop(m.get("req"), None)
                if fut and not fut.done():
                    if m.get("error"):
                        fut.set_exception(VoiceError(m["error"]))
                    else:
                        fut.set_result(m)
            elif kind == "roster":
                self.users = {u["id"]: u for u in m.get("users", [])}
                self.groups = m.get("groups", [])
                self.sync_needed.set()
                self.on_change()
            elif kind == "talk":
                if m.get("id") in self.users:
                    self.users[m["id"]]["talking"] = bool(m.get("on"))
                    self.on_change()
            elif kind == "pos":
                self.pos = {row[0]: row[1:] for row in m.get("list", [])}
                self.sync_needed.set()
                self._update_mix()
            elif kind in ("left", "revoke"):
                owner = m.get("id") if kind == "left" else m.get("owner")
                if kind == "left":
                    self.users.pop(owner, None)
                if owner in self.subs:
                    self.sync_needed.set()
            elif kind == "voice_muted":
                self.voice_muted_until = m.get("until")
                self.on_change()
            elif kind == "closed":
                self.closed_reason = m.get("reason") or "Voice was closed."
        if not hello.done():
            hello.set_exception(VoiceError("Voice didn't answer"))

    def _send_state(self, **patch):
        if self.ws is not None and not self.ws.closed:
            asyncio.ensure_future(self.ws.send_json({"type": "state", **patch}))

    async def request(self, kind, **data):
        if self.ws is None or self.ws.closed:
            raise VoiceError("Not connected")
        self.req += 1
        req = self.req
        fut = asyncio.get_running_loop().create_future()
        self.pending[req] = fut
        await self.ws.send_json({"type": kind, "req": req, **data})
        try:
            return await asyncio.wait_for(fut, 15)
        except asyncio.TimeoutError:
            self.pending.pop(req, None)
            raise VoiceError("Voice didn't answer")

    async def _ping_loop(self, ws):
        while True:
            await asyncio.sleep(30)
            await ws.send_str("ping")

    async def _cleanup(self):
        self.connected = False
        for t in self.readers.values():
            t.cancel()
        self.readers.clear()
        self.subs.clear()
        self.mid_owner.clear()
        for fut in self.pending.values():
            if not fut.done():
                fut.set_exception(VoiceError("Disconnected"))
        self.pending.clear()
        if self.pc:
            try:
                await self.pc.close()
            except Exception:
                pass
        self.pc = None
        if self.ws is not None:
            try:
                await self.ws.close()
            except Exception:
                pass
        self.ws = None
        self.audio.stop()

    # ---------- WebRTC (same steps as setupRtc / pull / closeSubs on the website) ----------

    async def _setup_rtc(self):
        await self.request("rtc.session")
        pc = RTCPeerConnection(RTCConfiguration(
            iceServers=[RTCIceServer(urls=STUN)] if STUN else [], bundlePolicy=RTCBundlePolicy.MAX_BUNDLE))
        self.pc = pc

        @pc.on("track")
        def on_track(track):
            mid = next((t.mid for t in pc.getTransceivers() if t.receiver.track is track), None)
            owner = self.mid_owner.get(mid)
            if owner is not None:
                name = self.users.get(owner, {}).get("username", owner)
                log.info("Hearing %s", name)
                old = self.readers.pop(owner, None)
                if old:
                    old.cancel()
                self.readers[owner] = asyncio.create_task(self._listen(owner, track))

        @pc.on("connectionstatechange")
        def on_state():
            log.info("Voice audio link: %s", pc.connectionState)
            if pc.connectionState == "connected":
                self.sync_needed.set()

        tx = pc.addTransceiver(MicTrack(self), direction="sendonly")
        await pc.setLocalDescription(await pc.createOffer())
        res = await self.request("rtc.push", sdp=pc.localDescription.sdp, mid=tx.mid)
        answer = res["answer"]
        await pc.setRemoteDescription(RTCSessionDescription(sdp=answer["sdp"], type=answer["type"]))

    async def _listen(self, owner, track):
        """Read one person's audio and hand it to the speaker mixer."""
        resampler = av.AudioResampler(format="flt", layout="mono", rate=RATE)
        self._update_mix()
        try:
            while True:
                frame = await track.recv()
                for f in resampler.resample(frame):
                    self.audio.add_voice(owner, f.to_ndarray().reshape(-1).astype(np.float32))
        except Exception:
            pass  # track ended
        finally:
            self.audio.remove_voice(owner)

    def can_hear(self, u, slack):
        """Mirrors the server's rules (the server double-checks)."""
        if u.get("id") == self.my_id or not u.get("published") or u.get("voiceMuted"):
            return False
        if u.get("global") and u.get("canGlobal"):
            return True
        mine = self.me().get("group")
        if mine and mine == u.get("group"):
            return True
        d = self.distance(u["id"])
        return d is not None and d <= self.range * slack

    def distance(self, owner):
        a, b = self.pos.get(self.my_id), self.pos.get(owner)
        if not a or not b or a[4] != b[4]:
            return None
        return math.dist(a[:3], b[:3])

    async def _sync_loop(self):
        """Pull people we can now hear, close people we can't. One change at a time."""
        while True:
            await self.sync_needed.wait()
            self.sync_needed.clear()
            if not self.pc or self.pc.connectionState != "connected":
                continue
            add = [u["id"] for u in self.users.values() if u["id"] not in self.subs and self.can_hear(u, 1.15)]
            remove = [o for o in self.subs if o not in self.users or not self.can_hear(self.users[o], 1.3)]
            if add or remove:
                log.info("Voice: listen to %s, stop %s", add, remove)
            try:
                async with self.rtc_lock:
                    if add:
                        await self._pull(add)
                    if remove:
                        await self._close(remove)
            except VoiceError as e:
                log.warning("Voice: %s", e)
            self._update_mix()
            await asyncio.sleep(0.3)

    async def _pull(self, owners):
        res = await self.request("rtc.pull", owners=owners)
        for t in res.get("tracks", []):
            self.mid_owner[t["mid"]] = t["owner"]
            self.subs[t["owner"]] = t["mid"]
        offer = res.get("offer")
        if offer:
            await self.pc.setRemoteDescription(RTCSessionDescription(sdp=offer["sdp"], type=offer["type"]))
            await self.pc.setLocalDescription(await self.pc.createAnswer())
            await self.request("rtc.renegotiate", sdp=self.pc.localDescription.sdp)

    async def _close(self, owners):
        mids = []
        for owner in owners:
            mid = self.subs.pop(owner, None)
            reader = self.readers.pop(owner, None)
            if reader:
                reader.cancel()
            self.audio.remove_voice(owner)
            if mid:
                mids.append(mid)
                self.mid_owner.pop(mid, None)
                for t in self.pc.getTransceivers():
                    if t.mid == mid and not t.stopped:
                        await t.stop()
        if not mids:
            return
        await self.pc.setLocalDescription(await self.pc.createOffer())
        res = await self.request("rtc.close", mids=mids, sdp=self.pc.localDescription.sdp)
        answer = res.get("answer")
        if answer:
            await self.pc.setRemoteDescription(RTCSessionDescription(sdp=answer["sdp"], type=answer["type"]))

    def _update_mix(self):
        """Volume of each person: full for group / Global Mic, otherwise by distance."""
        mine = self.me().get("group")
        for owner in list(self.subs):
            u = self.users.get(owner)
            gain = 0.0
            if u and not self.deafened:
                if (u.get("global") and u.get("canGlobal")) or (mine and mine == u.get("group")):
                    gain = 1.0
                else:
                    d = self.distance(owner)
                    gain = distance_gain(d, self.range) if d is not None else 0.0
            self.audio.gains[owner] = gain

    # ---------- "talking" icon for others ----------

    async def _talk_loop(self):
        while True:
            await asyncio.sleep(0.08)
            self._check_talking()

    def _check_talking(self):
        if self.ptt:
            talking = self.transmitting()
        else:
            now = time.monotonic()
            if self.transmitting() and self.audio.level > TALK_LEVEL:
                self.talk_until = now + 0.4
            talking = self.transmitting() and now < self.talk_until
        if talking != self.talking:
            self.talking = talking
            self._send_state(talking=talking)
            self.on_change()
