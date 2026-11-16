"""Microphone and speaker / headset for voice chat (spec §8).

Everything is 48 kHz mono, in 20 ms frames of 960 samples (what Opus uses).
Auto picks the USB headset when it's plugged in, otherwise the built-in mic and speaker.
Fake mode: the mic sends silence and the speaker throws the sound away (but counts it, for tests).
"""
import asyncio
import collections

import numpy as np

from .. import config

log = config.log
RATE = 48000
FRAME = 960                 # 20 ms
GATE = 0.012                # built-in mic: quieter than this counts as silence (stops fan / room noise)


def find_devices(choice):
    """Return (mic, speaker, kind) for "Auto" / "Headset" / "Speaker".

    Built-in = the I2S mic + amp inside the Cube. USB = a headset adapter, or a plug-in USB mic and USB
    speaker (they can be two different devices). Auto uses USB when something USB is plugged in.
    kind is "headset" (no echo worries) or "speaker" (noise gate on, push-to-talk recommended).
    """
    if config.FAKE:
        return None, None, "headset" if choice == "Headset" else "speaker"
    import sounddevice as sd
    usb_in = usb_out = builtin = None
    for i, d in enumerate(sd.query_devices()):
        name = d["name"].lower()
        if "usb" in name:
            if d["max_input_channels"] and usb_in is None:
                usb_in = i
            if d["max_output_channels"] and usb_out is None:
                usb_out = i
        elif ("voicehat" in name or "i2s" in name or "googlevoice" in name) and builtin is None:
            builtin = i
    use_usb = choice == "Headset" or (choice == "Auto" and (usb_in is not None or usb_out is not None))
    if choice == "Speaker" or not use_usb:
        return builtin, builtin, "speaker"
    mic = usb_in if usb_in is not None else builtin
    out = usb_out if usb_out is not None else builtin
    # one USB device with both jacks = a headset adapter; anything else can echo like a speaker
    kind = "headset" if mic == out and mic is not None else "speaker"
    return mic, out, kind


class Audio:
    def __init__(self):
        self.mic = asyncio.Queue(maxsize=10)        # 20 ms frames from the microphone (int16)
        self.voices = {}                            # owner id -> deque of float frames
        self.gains = {}                             # owner id -> 0..1
        self.volume = 0.8
        self.kind = "speaker"
        self.level = 0.0                            # how loud the mic is now (0..1), for "talking" detection
        self.played_frames = 0                      # for tests
        self.loop = None
        self.streams = []

    def start(self, choice):
        self.loop = asyncio.get_running_loop()
        mic_dev, out_dev, self.kind = find_devices(choice)
        log.info("Voice audio: %s", self.kind)
        if config.FAKE:
            self.fake_task = asyncio.create_task(self._fake_clock())
            return
        import sounddevice as sd
        stream_in = sd.InputStream(device=mic_dev, samplerate=RATE, channels=1, dtype="int16",
                                   blocksize=FRAME, callback=self._on_mic)
        stream_out = sd.OutputStream(device=out_dev, samplerate=RATE, channels=1, dtype="int16",
                                     blocksize=FRAME, callback=self._on_speaker)
        stream_in.start()
        stream_out.start()
        self.streams = [stream_in, stream_out]

    def stop(self):
        for s in self.streams:
            try:
                s.stop()
                s.close()
            except Exception:
                pass
        self.streams = []
        if config.FAKE and getattr(self, "fake_task", None):
            self.fake_task.cancel()
        self.voices.clear()

    # ---- microphone ----

    def _on_mic(self, data, frames, time, status):
        pcm = data[:, 0].copy()
        self.loop.call_soon_threadsafe(self._mic_frame, pcm)

    def _mic_frame(self, pcm):
        self.level = float(np.sqrt(np.mean((pcm.astype(np.float32) / 32768) ** 2)))
        if self.kind == "speaker" and self.level < GATE:
            pcm = np.zeros(FRAME, np.int16)
        if self.mic.full():
            self.mic.get_nowait()  # never fall behind: drop the oldest frame
        self.mic.put_nowait(pcm)

    async def _fake_clock(self):
        """Fake mode: a pretend mic (silence) and speaker, both running in real time."""
        while True:
            await asyncio.sleep(FRAME / RATE)
            self._mic_frame(np.zeros(FRAME, np.int16))
            self._on_speaker(np.zeros((FRAME, 1), np.int16), FRAME, None, None)

    # ---- speaker: mix everyone we can hear ----

    def add_voice(self, owner, pcm):
        """pcm: float32 mono 48 kHz, any length."""
        q = self.voices.setdefault(owner, collections.deque())
        q.append(pcm)
        while sum(len(x) for x in q) > RATE // 4:   # keep at most 250 ms waiting (low delay)
            q.popleft()

    def remove_voice(self, owner):
        self.voices.pop(owner, None)
        self.gains.pop(owner, None)

    def _take(self, q, n):
        out = np.zeros(n, np.float32)
        filled = 0
        while q and filled < n:
            chunk = q[0]
            take = min(n - filled, len(chunk))
            out[filled:filled + take] = chunk[:take]
            filled += take
            if take == len(chunk):
                q.popleft()
            else:
                q[0] = chunk[take:]
        return out

    def _on_speaker(self, outdata, frames, time, status):
        mix = np.zeros(frames, np.float32)
        for owner, q in list(self.voices.items()):
            gain = self.gains.get(owner, 0.0)
            chunk = self._take(q, frames)
            if gain > 0:
                mix += chunk * gain
        mix *= self.volume
        outdata[:, 0] = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
        if mix.any():
            self.played_frames += 1
