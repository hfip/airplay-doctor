"""Minimal mDNS and port checks for AirPlay debugging."""

from __future__ import annotations

import socket
import struct
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

TYPE_A = 1
TYPE_PTR = 12
TYPE_SRV = 33
TYPE_AAAA = 28


@dataclass
class Record:
    name: str
    kind: int
    value: str


@dataclass
class Device:
    name: str
    address: Optional[str] = None
    port: Optional[int] = None
    records: List[Record] = field(default_factory=list)


def encode_name(name: str) -> bytes:
    output = b""
    for label in name.rstrip(".").split("."):
        encoded = label.encode("utf-8")
        output += bytes([len(encoded)]) + encoded
    return output + b"\x00"


def build_ptr_query(service: str, txid: int = 0) -> bytes:
    header = struct.pack(">HHHHHH", txid, 0, 1, 0, 0, 0)
    question = encode_name(service) + struct.pack(">HH", TYPE_PTR, 1)
    return header + question


def read_name(data: bytes, offset: int) -> Tuple[str, int]:
    labels: List[str] = []
    next_offset = offset
    jumped = False
    guard = 0

    while True:
        if offset >= len(data):
            break
        length = data[offset]
        if length == 0:
            offset += 1
            if not jumped:
                next_offset = offset
            break
        if length & 0xC0 == 0xC0:
            pointer = ((length & 0x3F) << 8) | data[offset + 1]
            if not jumped:
                next_offset = offset + 2
            jumped = True
            offset = pointer
            guard += 1
            if guard > 32:
                break
            continue
        labels.append(data[offset + 1 : offset + 1 + length].decode("utf-8", errors="replace"))
        offset += 1 + length
        if not jumped:
            next_offset = offset

    return ".".join(labels), next_offset


def parse_response(data: bytes) -> List[Record]:
    if len(data) < 12:
        return []
    _, _, questions, answers, _, _ = struct.unpack(">HHHHHH", data[:12])
    offset = 12
    for _ in range(questions):
        _, offset = read_name(data, offset)
        offset += 4

    records: List[Record] = []
    for _ in range(answers):
        name, offset = read_name(data, offset)
        if offset + 10 > len(data):
            break
        kind, _, _, length = struct.unpack(">HHIH", data[offset : offset + 10])
        offset += 10
        rdata = data[offset : offset + length]
        offset += length

        if kind == TYPE_PTR:
            value, _ = read_name(data, offset - length)
            records.append(Record(name=name, kind=kind, value=value))
        elif kind == TYPE_A and len(rdata) == 4:
            records.append(Record(name=name, kind=kind, value=socket.inet_ntoa(rdata)))
        elif kind == TYPE_AAAA and len(rdata) == 16:
            records.append(
                Record(name=name, kind=kind, value=socket.inet_ntop(socket.AF_INET6, rdata))
            )
        elif kind == TYPE_SRV and len(rdata) >= 7:
            _, _, port = struct.unpack(">HHH", rdata[:6])
            target, _ = read_name(data, offset - length + 6)
            records.append(Record(name=name, kind=kind, value="%s:%d" % (target, port)))

    return records


def discover(service: str = "_airplay._tcp.local", timeout: float = 3.0) -> List[Record]:
    query = build_ptr_query(service)
    records: List[Record] = []
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(timeout)
        sock.sendto(query, ("224.0.0.251", 5353))
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                payload, _ = sock.recvfrom(9000)
            except socket.timeout:
                break
            records.extend(parse_response(payload))
        sock.close()
    except OSError:
        return records
    return records


def devices(records: Sequence[Record]) -> Dict[str, Device]:
    services = {record.value for record in records if record.kind == TYPE_PTR}
    targets = {record.name: record.value for record in records if record.kind == TYPE_SRV}
    addresses = {
        record.name: record.value for record in records if record.kind in (TYPE_A, TYPE_AAAA)
    }

    found: Dict[str, Device] = {}
    for service in services:
        target, port = None, None
        if service in targets:
            host, _, port_text = targets[service].rpartition(":")
            target = host
            try:
                port = int(port_text)
            except ValueError:
                port = None
        address = addresses.get(target) if target else None
        found[service] = Device(name=service, address=address, port=port)
    return found


def check_port(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def local_addresses() -> List[Tuple[str, str]]:
    addresses: List[Tuple[str, str]] = []
    try:
        for index, name in socket.if_nameindex():
            addresses.append((name, ""))
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if address not in ("127.0.0.1",):
                addresses.append(("host", address))
                break
    except OSError:
        pass
    return addresses
