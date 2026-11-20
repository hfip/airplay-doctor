"""Command line interface for airplay-doctor."""

from __future__ import annotations

import argparse
import json
from typing import Iterable, Optional

from . import __version__
from .network import check_port, devices, discover, local_addresses

PORTS = (
    (7000, "airplay"),
    (7001, "airplay (event)"),
    (5000, "raop"),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="airplay-doctor",
        description="Diagnose AirPlay connectivity: local interfaces, open ports and mDNS.",
    )
    parser.add_argument("--device", metavar="IP", help="Apple TV address to test")
    parser.add_argument("--timeout", type=float, default=3.0, help="mDNS listen time in seconds")
    parser.add_argument("--no-mdns", action="store_true", help="skip mDNS discovery")
    parser.add_argument(
        "--strict", action="store_true", help="exit 1 when the device has no open port"
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "-V", "--version", action="version", version="airplay-doctor " + __version__
    )
    return parser


def gather(device: Optional[str], timeout: float, use_mdns: bool) -> dict:
    report = {
        "interfaces": [{"name": name, "address": address} for name, address in local_addresses()],
        "ports": [],
        "devices": [],
    }
    if device:
        for port, label in PORTS:
            report["ports"].append(
                {"port": port, "label": label, "open": check_port(device, port, timeout=1.0)}
            )
    if use_mdns:
        found = devices(discover(timeout=timeout))
        report["devices"] = [
            {"name": item.name, "address": item.address, "port": item.port}
            for item in found.values()
        ]
    return report


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = gather(args.device, args.timeout, not args.no_mdns)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print("interfaces")
        seen = set()
        for item in report["interfaces"]:
            label = item["name"]
            if label in seen:
                continue
            seen.add(label)
            print("  %-10s %s" % (label, item["address"] or "-"))
        if not report["interfaces"]:
            print("  none found")

        if args.device:
            print()
            print("ports on %s" % args.device)
            for item in report["ports"]:
                state = "open  " if item["open"] else "closed"
                print("  %-5d %s  %s" % (item["port"], state, item["label"]))

        if not args.no_mdns:
            print()
            print("mDNS (_airplay._tcp.local)")
            if report["devices"]:
                for item in report["devices"]:
                    address = item["address"] or "?"
                    print("  %-40s %s:%s" % (item["name"], address, item["port"] or "?"))
            else:
                print("  no devices answered")
                print(
                    "  if the Apple TV is visible in the picker, mDNS is being filtered on this network"
                )

        if not args.device and not report["devices"]:
            print()
            print("hint: pass --device <apple-tv-ip> to check the known AirPlay ports")

    if args.strict and args.device and not any(item["open"] for item in report["ports"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
