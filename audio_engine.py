"""
audio_engine.py
Handles microphone capture, Opus encode/decode, and speaker playback.

READ THIS BEFORE DEPLOYING TO A PHONE:
- Uses `sounddevice` + `opuslib`, which are great for DESKTOP TESTING
  (Windows/Mac/Linux) -- you can prototype the whole app on two laptops
  on the same Wi-Fi network before touching a phone at all.
- Neither PyAudio nor sounddevice has an official python-for-android
  recipe, so they will NOT build with Buildozer as-is. For a real
  Android build, swap the capture/playback calls in this file for
  either:
    a) the `audiostream` package (has a working p4a recipe, built by
       the Kivy team for exactly this kind of low-latency streaming), or
    b) direct pyjnius calls to android.media.AudioRecord / AudioTrack.
  Everything else here (20ms framing, Opus, threading, queues) stays
  the same either way -- only the capture/playback backend changes.
- opuslib also has no official p4a recipe. If it fails to import, this
  file automatically falls back to sending raw 16-bit PCM frames
  (bigger packets, more bandwidth, but still works -- fine for a local
  hotspot with a handful of peers).
"""

import threading
import queue

import numpy as np
import sounddevice as sd

try:
    import opuslib
    OPUS_AVAILABLE = True
except ImportError:
    OPUS_AVAILABLE = False


SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_MS = 20
FRAME_SIZE = int(SAMPLE_RATE * FRAME_MS / 1000)  # 320 samples/frame


class AudioEngine:
    def __init__(self, on_encoded_frame=None):
        """
        on_encoded_frame: callback(bytes) fired for every outgoing
        encoded (or raw PCM fallback) audio frame while transmitting.
        """
        self.on_encoded_frame = on_encoded_frame

        self._capture_stream = None
        self._playback_thread = None
        self._playback_queue = queue.Queue()
        self._playing = False

        if OPUS_AVAILABLE:
            self.encoder = opuslib.Encoder(SAMPLE_RATE, CHANNELS, opuslib.APPLICATION_VOIP)
            self.decoder = opuslib.Decoder(SAMPLE_RATE, CHANNELS)
        else:
            self.encoder = None
            self.decoder = None

    # ---------------- Capture (Push-to-Talk) ----------------

    def start_capture(self):
        if self._capture_stream is not None:
            return

        def _callback(indata, frames, time_info, status):
            pcm_bytes = indata.tobytes()
            if OPUS_AVAILABLE:
                try:
                    payload = self.encoder.encode(pcm_bytes, FRAME_SIZE)
                except Exception:
                    payload = pcm_bytes  # fall back if a partial frame slips through
            else:
                payload = pcm_bytes
            if self.on_encoded_frame:
                self.on_encoded_frame(payload)

        self._capture_stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=FRAME_SIZE,
            callback=_callback,
        )
        self._capture_stream.start()

    def stop_capture(self):
        if self._capture_stream is not None:
            self._capture_stream.stop()
            self._capture_stream.close()
            self._capture_stream = None

    # ---------------- Playback (receiving) ----------------

    def start_playback(self):
        if self._playing:
            return
        self._playing = True
        self._playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._playback_thread.start()

    def stop_playback(self):
        self._playing = False
        self._playback_queue.put(None)  # unblock the loop so the thread can exit

    def push_incoming_frame(self, payload: bytes):
        """Call this from the network layer whenever a UDP packet arrives."""
        self._playback_queue.put(payload)

    def _playback_loop(self):
        with sd.OutputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16") as out:
            while self._playing:
                payload = self._playback_queue.get()
                if payload is None:
                    continue
                if OPUS_AVAILABLE:
                    try:
                        pcm_bytes = self.decoder.decode(payload, FRAME_SIZE)
                    except Exception:
                        pcm_bytes = payload  # assume it was a raw-PCM fallback frame
                else:
                    pcm_bytes = payload
                samples = np.frombuffer(pcm_bytes, dtype=np.int16).reshape(-1, CHANNELS)
                out.write(samples)