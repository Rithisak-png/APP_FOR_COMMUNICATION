"""
network_engine.py
Local-network peer discovery (zeroconf/mDNS) + UDP audio transport.

Everything here runs on the LAN created by a phone's Wi-Fi hotspot -- no
internet, no cloud server. Each peer advertises a
_walkietalkie._udp.local. mDNS service so nobody has to type IP addresses,
and audio frames travel as plain UDP datagrams for minimum latency.
"""

import socket
import threading
import uuid

from zeroconf import ServiceInfo, ServiceBrowser, ServiceListener, Zeroconf

SERVICE_TYPE = "_walkietalkie._udp.local."
UDP_PORT = 50505


def get_local_ip():
    """Best-effort local IP on the hotspot subnet (no internet needed)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.168.1.1", 1))  # doesn't actually send any packet
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


class NetworkEngine:
    def __init__(self, display_name, on_peer_list_changed=None, on_audio_received=None):
        self.display_name = display_name
        self.device_id = f"{display_name}-{uuid.uuid4().hex[:6]}"
        self.on_peer_list_changed = on_peer_list_changed
        self.on_audio_received = on_audio_received

        self.local_ip = get_local_ip()
        self.udp_port = UDP_PORT

        self.peers = {}  # device_id -> (ip, port, display_name)
        self._peers_lock = threading.Lock()

        self._sock = None
        self._recv_thread = None
        self._running = False

        self._zeroconf = None
        self._service_info = None
        self._browser = None

    # ---------------- Discovery ----------------

    def start_discovery(self):
        self._zeroconf = Zeroconf()

        self._service_info = ServiceInfo(
            SERVICE_TYPE,
            f"{self.device_id}.{SERVICE_TYPE}",
            addresses=[socket.inet_aton(self.local_ip)],
            port=self.udp_port,
            properties={"name": self.display_name},
        )
        self._zeroconf.register_service(self._service_info)

        listener = _PeerListener(self)
        self._browser = ServiceBrowser(self._zeroconf, SERVICE_TYPE, listener)

    def stop_discovery(self):
        if self._zeroconf:
            if self._service_info:
                self._zeroconf.unregister_service(self._service_info)
            self._zeroconf.close()
            self._zeroconf = None

    def _add_peer(self, device_id, ip, port, name):
        with self._peers_lock:
            self.peers[device_id] = (ip, port, name)
        self._notify_peers_changed()

    def _remove_peer(self, device_id):
        with self._peers_lock:
            self.peers.pop(device_id, None)
        self._notify_peers_changed()

    def _notify_peers_changed(self):
        if self.on_peer_list_changed:
            with self._peers_lock:
                snapshot = dict(self.peers)
            self.on_peer_list_changed(snapshot)

    # ---------------- UDP transport ----------------

    def start_udp(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("0.0.0.0", self.udp_port))
        self._running = True
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread.start()

    def stop_udp(self):
        self._running = False
        if self._sock:
            self._sock.close()
            self._sock = None

    def _recv_loop(self):
        while self._running:
            try:
                data, addr = self._sock.recvfrom(4096)
            except OSError:
                break
            if self.on_audio_received:
                self.on_audio_received(data, addr)

    def send_audio(self, payload: bytes):
        """Fan the frame out to every currently known peer (broadcast-style)."""
        if not self._sock:
            return
        with self._peers_lock:
            targets = [(ip, port) for ip, port, _ in self.peers.values()]
        for ip, port in targets:
            try:
                self._sock.sendto(payload, (ip, port))
            except OSError:
                pass


class _PeerListener(ServiceListener):
    def __init__(self, engine: NetworkEngine):
        self.engine = engine

    def add_service(self, zeroconf, type_, name):
        info = zeroconf.get_service_info(type_, name)
        if not info or name.startswith(self.engine.device_id):
            return
        ip = socket.inet_ntoa(info.addresses[0])
        display_name = info.properties.get(b"name", b"Unknown").decode()
        device_id = name.split(f".{SERVICE_TYPE}")[0]
        self.engine._add_peer(device_id, ip, info.port, display_name)

    def update_service(self, zeroconf, type_, name):
        self.add_service(zeroconf, type_, name)

    def remove_service(self, zeroconf, type_, name):
        device_id = name.split(f".{SERVICE_TYPE}")[0]
        self.engine._remove_peer(device_id)