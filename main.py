"""
main.py
Offline local-Wi-Fi walkie-talkie -- Kivy app entry point.

QUICK TEST (no phone or hotspot needed):
  1. pip install kivy sounddevice numpy zeroconf opuslib
     (opuslib is optional -- the app falls back to raw PCM if it's missing)
  2. Run this file on two laptops connected to the same Wi-Fi network.
  3. Tap "START DISCOVERY" on both, wait for peers to appear, hold PTT.

Moving to a real Android build: see the notes at the top of
audio_engine.py -- sounddevice/PyAudio need to be swapped for an
Android-native audio backend (audiostream or pyjnius) before this will
run inside a Buildozer APK.
"""

import socket

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.factory import Factory

from audio_engine import AudioEngine
from network_engine import NetworkEngine

Builder.load_file("walkie.kv")


class RootWidget(BoxLayout):
    pass


class WalkieApp(App):
    def build(self):
        self.display_name = socket.gethostname()
        self.root_widget = RootWidget()

        self.network = NetworkEngine(
            display_name=self.display_name,
            on_peer_list_changed=self._on_peer_list_changed,
            on_audio_received=self._on_audio_received,
        )
        self.audio = AudioEngine(on_encoded_frame=self._on_encoded_frame)

        self.discovery_active = False
        self._talking = False

        return self.root_widget

    # ---------------- Discovery / networking lifecycle ----------------

    def toggle_discovery(self):
        if not self.discovery_active:
            self.network.start_udp()
            self.network.start_discovery()
            self.audio.start_playback()
            self.discovery_active = True
            self._set_state("DISCOVERING")
            self.root_widget.ids.hotspot_button.text = "STOP DISCOVERY"
        else:
            self.network.stop_discovery()
            self.network.stop_udp()
            self.audio.stop_playback()
            self.discovery_active = False
            self._set_state("IDLE")
            self.root_widget.ids.hotspot_button.text = "START DISCOVERY"

    # ---------------- Push-to-talk ----------------

    def on_ptt_press(self):
        if not self.discovery_active:
            return
        self._talking = True
        self.audio.start_capture()
        self._set_state("TRANSMITTING")

    def on_ptt_release(self):
        self._talking = False
        self.audio.stop_capture()
        self._set_state("LISTENING" if self.discovery_active else "IDLE")

    def _on_encoded_frame(self, payload: bytes):
        # Called from the audio capture thread. socket.sendto is thread-safe,
        # so we can call straight into the network engine without hopping
        # back onto the Kivy/main thread first.
        self.network.send_audio(payload)

    # ---------------- Incoming audio ----------------

    def _on_audio_received(self, data: bytes, addr):
        self.audio.push_incoming_frame(data)
        Clock.schedule_once(lambda dt: self._flash_listening(addr), 0)

    def _flash_listening(self, addr):
        if not self._talking:
            self._set_state(f"LISTENING ({addr[0]})")
            Clock.unschedule(self._reset_to_idle)
            Clock.schedule_once(self._reset_to_idle, 1.5)

    def _reset_to_idle(self, dt):
        if not self._talking:
            self._set_state("DISCOVERING" if self.discovery_active else "IDLE")

    # ---------------- Peers list UI ----------------

    def _on_peer_list_changed(self, peers: dict):
        Clock.schedule_once(lambda dt: self._render_peers(peers), 0)

    def _render_peers(self, peers: dict):
        box = self.root_widget.ids.peers_box
        box.clear_widgets()
        for device_id, (ip, port, name) in peers.items():
            row = Factory.PeerRow()
            row.name = f"{name}  ({ip})"
            box.add_widget(row)

    # ---------------- Helpers ----------------

    def _set_state(self, text: str):
        self.root_widget.ids.state_label.text = f"STATE: {text}"


if __name__ == "__main__":
    WalkieApp().run()