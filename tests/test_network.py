import json
import socket
import struct

from airplay_doctor.network import (
    Device,
    build_ptr_query,
    check_port,
    devices,
    encode_name,
    parse_response,
    read_name,
)
from airplay_doctor.cli import main


def make_record(name, kind, rdata):
    return encode_name(name) + struct.pack(">HHIH", kind, 1, 60, len(rdata)) + rdata


def make_response(answers):
    return struct.pack(">HHHHHH", 0, 0x8400, 0, len(answers), 0, 0) + b"".join(answers)


def sample_response():
    ptr = make_record(
        "_airplay._tcp.local",
        12,
        encode_name("Living Room._airplay._tcp.local"),
    )
    srv = make_record(
        "Living Room._airplay._tcp.local",
        33,
        struct.pack(">HHH", 0, 0, 7000) + encode_name("living.local"),
    )
    a = make_record("living.local", 1, socket.inet_aton("10.0.0.42"))
    return make_response([ptr, srv, a])


def test_encode_name():
    assert encode_name("_airplay._tcp.local") == (b"\x08_airplay\x04_tcp\x05local\x00")


def test_build_query_has_ptr_question():
    query = build_ptr_query("_airplay._tcp.local")
    assert query[:12] == struct.pack(">HHHHHH", 0, 0, 1, 0, 0, 0)
    assert query.endswith(struct.pack(">HH", 12, 1))


def test_parse_ptr_answer():
    records = parse_response(sample_response())
    ptr = [record for record in records if record.kind == 12]
    assert ptr[0].value == "Living Room._airplay._tcp.local"


def test_parse_address_and_service():
    records = parse_response(sample_response())
    assert any(record.kind == 1 and record.value == "10.0.0.42" for record in records)
    assert any("7000" in record.value for record in records if record.kind == 33)


def test_devices_join_srv_and_address():
    found = devices(parse_response(sample_response()))
    device = found["Living Room._airplay._tcp.local"]
    assert device == Device(name="Living Room._airplay._tcp.local", address="10.0.0.42", port=7000)


def test_read_name_follows_compression_pointer():
    label = encode_name("_airplay._tcp.local")
    data = b"\x00" * 12 + label + b"\xc0\x0c"
    name, offset = read_name(data, 12 + len(label))
    assert name == "_airplay._tcp.local"
    assert offset == 12 + len(label) + 2


def test_parse_garbage_returns_nothing():
    assert parse_response(b"") == []
    assert parse_response(b"\x00" * 4) == []


def test_check_port_detects_listening_socket():
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    try:
        assert check_port("127.0.0.1", port) is True
    finally:
        server.close()


def test_check_port_reports_closed_port():
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    assert check_port("127.0.0.1", port, timeout=0.2) is False


def test_cli_json(monkeypatch, capsys):
    monkeypatch.setattr("airplay_doctor.cli.interface_names", lambda: ["eth0"])
    monkeypatch.setattr("airplay_doctor.cli.local_addresses", lambda: ["10.0.0.5"])
    monkeypatch.setattr("airplay_doctor.cli.discover", lambda timeout: [])
    monkeypatch.setattr("airplay_doctor.cli.check_port", lambda host, port, timeout=1.0: False)
    assert main(["--json", "--device", "10.0.0.42"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["interfaces"] == ["eth0"]
    assert payload["addresses"] == ["10.0.0.5"]
    assert len(payload["ports"]) == 3


def test_cli_no_mdns_does_not_discover(monkeypatch, capsys):
    def explode(timeout):
        raise AssertionError("mDNS should not run")

    monkeypatch.setattr("airplay_doctor.cli.interface_names", lambda: [])
    monkeypatch.setattr("airplay_doctor.cli.local_addresses", lambda: [])
    monkeypatch.setattr("airplay_doctor.cli.discover", explode)
    assert main(["--no-mdns"]) == 0
    assert "mDNS" not in capsys.readouterr().out


def test_cli_strict_fails_when_no_port_is_open(monkeypatch):
    monkeypatch.setattr("airplay_doctor.cli.interface_names", lambda: [])
    monkeypatch.setattr("airplay_doctor.cli.local_addresses", lambda: [])
    monkeypatch.setattr("airplay_doctor.cli.discover", lambda timeout: [])
    monkeypatch.setattr("airplay_doctor.cli.check_port", lambda host, port, timeout=1.0: False)
    assert main(["--no-mdns", "--strict", "--device", "10.0.0.42"]) == 1


def test_cli_strict_passes_with_one_open_port(monkeypatch):
    monkeypatch.setattr("airplay_doctor.cli.interface_names", lambda: [])
    monkeypatch.setattr("airplay_doctor.cli.local_addresses", lambda: [])
    monkeypatch.setattr("airplay_doctor.cli.discover", lambda timeout: [])
    monkeypatch.setattr(
        "airplay_doctor.cli.check_port",
        lambda host, port, timeout=1.0: port == 7000,
    )
    assert main(["--no-mdns", "--strict", "--device", "10.0.0.42"]) == 0
