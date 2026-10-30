"""LAN IPv4 discovery, UNO Q network resolution, and QR code generation for The Last Clue."""

from __future__ import annotations

import ipaddress
import logging
import os
import re
import socket
import subprocess

from last_clue.qr_svg import generate_qr_png, generate_qr_svg

logger = logging.getLogger(__name__)

# Virtual / container interfaces to deprioritize or ignore when detecting LAN Wi-Fi IPs
_VIRTUAL_IFACE_PREFIXES = (
    "lo",
    "docker",
    "br-",
    "veth",
    "cni",
    "flannel",
    "virbr",
    "utun",
    "awdl",
    "llw",
    "bridge",
    "tun",
    "tap",
)

_PREFERRED_IFACE_PREFIXES = (
    "wlan",
    "wlp",
    "wl",
    "en0",
    "en1",
    "eth",
    "enp",
)


def _is_usable_lan_ip(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr.strip())
    except ValueError:
        return False
    if ip.version != 4:
        return False
    if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
        return False
    # Exclude standard Docker bridge subnets (172.17.0.0/16, 172.18.0.0/16) when checking LAN
    octets = addr.strip().split(".")
    if len(octets) == 4 and octets[0] == "172" and octets[1] in {"17", "18"}:
        return False
    return True


def _score_ip(addr: str, iface: str = "") -> int:
    """Rank candidate IPv4 addresses so physical Wi-Fi / LAN addresses win."""
    score = 0
    iface_low = iface.lower()
    if any(iface_low.startswith(p) for p in _PREFERRED_IFACE_PREFIXES):
        score += 50
    if addr.startswith("192.168."):
        score += 30
    elif addr.startswith("10."):
        score += 20
    elif addr.startswith("172."):
        score += 5
    return score


def detect_lan_ips() -> list[str]:
    """Detect reachable non-loopback IPv4 addresses on Arduino UNO Q or macOS."""
    candidates: dict[str, int] = {}

    # 1. Explicit environment override (LAST_CLUE_PUBLIC_HOST or HOST_IP)
    for env_key in ("LAST_CLUE_PUBLIC_HOST", "HOST_IP"):
        env_val = os.environ.get(env_key, "").strip()
        if env_val and _is_usable_lan_ip(env_val):
            candidates[env_val] = 200

    # 2. Linux `ip -4 -o addr show` (available on Arduino UNO Q Debian Linux MPU)
    try:
        proc = subprocess.run(
            ["ip", "-4", "-o", "addr", "show"],
            capture_output=True,
            text=True,
            timeout=0.8,
            check=False,
        )
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 4:
                    iface = parts[1]
                    if any(iface.lower().startswith(p) for p in _VIRTUAL_IFACE_PREFIXES):
                        continue
                    match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", line)
                    if match:
                        addr = match.group(1)
                        if _is_usable_lan_ip(addr):
                            candidates[addr] = max(
                                candidates.get(addr, 0), _score_ip(addr, iface)
                            )
    except (OSError, subprocess.SubprocessError):
        pass

    # 3. macOS / BSD `ifconfig` fallback
    if not candidates:
        try:
            proc = subprocess.run(
                ["ifconfig"],
                capture_output=True,
                text=True,
                timeout=0.8,
                check=False,
            )
            if proc.returncode == 0:
                current_iface = ""
                for line in proc.stdout.splitlines():
                    if line and not line[0].isspace() and ":" in line:
                        current_iface = line.split(":", 1)[0].strip()
                    elif "inet " in line:
                        if any(
                            current_iface.lower().startswith(p)
                            for p in _VIRTUAL_IFACE_PREFIXES
                        ):
                            continue
                        match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", line)
                        if match:
                            addr = match.group(1)
                            if _is_usable_lan_ip(addr):
                                candidates[addr] = max(
                                    candidates.get(addr, 0),
                                    _score_ip(addr, current_iface),
                                )
        except (OSError, subprocess.SubprocessError):
            pass

    # 4. UDP routing table probes across common LAN gateways
    for probe_target in ("192.168.1.1", "10.255.255.255", "8.8.8.8"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(0.15)
                s.connect((probe_target, 80))
                addr = s.getsockname()[0]
                if _is_usable_lan_ip(addr):
                    candidates[addr] = max(candidates.get(addr, 0), _score_ip(addr) + 10)
        except OSError:
            pass

    # 5. Hostname resolution fallback
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            addr = str(info[4][0])
            if _is_usable_lan_ip(addr):
                candidates[addr] = max(candidates.get(addr, 0), _score_ip(addr))
    except OSError:
        pass

    ordered = sorted(candidates.keys(), key=lambda a: (-candidates[a], a))
    return ordered


def extract_non_loopback_host(raw_host: str | None) -> str | None:
    """Extract a clean hostname or LAN IP from an HTTP Host header if it is not loopback."""
    if not raw_host:
        return None
    cleaned = raw_host.strip()
    if "://" in cleaned:
        cleaned = cleaned.split("://", 1)[1]
    cleaned = cleaned.split("/", 1)[0].strip()
    if cleaned.startswith("["):
        return None
    host_only = cleaned.split(":", 1)[0].strip()
    if not host_only:
        return None
    lowered = host_only.lower()
    if lowered in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} or lowered.startswith("127."):
        return None
    return host_only


def resolve_join_url(
    port: int,
    room_code: str | None = None,
    *,
    request_host: str | None = None,
    preferred_host: str | None = None,
) -> tuple[str, bool, str | None]:
    """Resolve the best network-accessible URL for sharing and QR code encoding.

    Returns ``(join_url, is_lan_reachable, warning_message)``.
    """
    explicit = extract_non_loopback_host(preferred_host)
    req_lan = extract_non_loopback_host(request_host)
    lan_ips = detect_lan_ips()

    chosen_host: str | None = None
    if explicit:
        chosen_host = explicit
    elif req_lan and _is_usable_lan_ip(req_lan):
        chosen_host = req_lan
    elif lan_ips:
        chosen_host = lan_ips[0]
    elif req_lan:
        chosen_host = req_lan

    if chosen_host:
        base = f"http://{chosen_host}:{port}"
        url = f"{base}/?room={room_code.upper()}" if room_code else base
        return url, True, None

    fallback_base = f"http://127.0.0.1:{port}"
    fallback_url = (
        f"{fallback_base}/?room={room_code.upper()}" if room_code else fallback_base
    )
    warning = (
        "No Wi-Fi / LAN address detected. Connect the Arduino UNO Q to Wi-Fi "
        "or enter the board's LAN IP so phones can scan the QR code."
    )
    return fallback_url, False, warning


def primary_join_url(
    port: int,
    room_code: str | None = None,
    *,
    request_host: str | None = None,
    preferred_host: str | None = None,
) -> str:
    """Return the primary LAN URL for players to scan or open on their phones."""
    url, _, _ = resolve_join_url(
        port,
        room_code,
        request_host=request_host,
        preferred_host=preferred_host,
    )
    return url


__all__ = [
    "detect_lan_ips",
    "extract_non_loopback_host",
    "generate_qr_png",
    "generate_qr_svg",
    "primary_join_url",
    "resolve_join_url",
]
