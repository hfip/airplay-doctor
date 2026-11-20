# airplay-doctor

AirPlay failing is almost never the app. It is the network: the Apple TV is on a guest
VLAN, the router filters multicast, or the device is asleep and not answering on 7000.

```
$ airplay-doctor --device 10.0.0.42
interfaces
  lo, en0, utun3
addresses
  10.0.0.5

ports on 10.0.0.42
  7000  open    airplay
  7001  closed  airplay (event)
  5000  closed  raop

mDNS (_airplay._tcp.local)
  Living Room._airplay._tcp.local          10.0.0.42:7000
```

## What it checks

1. **Interfaces.** Which local addresses exist, so you can see whether the Mac and the Apple
   TV are even on the same subnet.
2. **AirPlay ports.** TCP 7000, 7001 and 5000 on the device you name.
3. **mDNS.** Sends a single PTR query for `_airplay._tcp.local` to `224.0.0.251:5353` and
   prints whatever answers, joining SRV and A records into `name address:port`.

The mDNS part is a real DNS packet, built and parsed in `network.py` with no dependencies.
That also means the parser is testable: the test suite feeds it crafted responses, including
compressed names.

## Install

```bash
pipx install git+https://github.com/hfip/airplay-doctor.git
```

Python 3.9+, standard library only.

## Use

```bash
airplay-doctor                              # interfaces and mDNS
airplay-doctor --device 10.0.0.42           # also probe ports
airplay-doctor --no-mdns --device 10.0.0.42 # ports only
airplay-doctor --json                       # for a bug report
airplay-doctor --strict --device 10.0.0.42  # exit 1 if nothing is open
```

## Reading the result

- **Port 7000 closed, mDNS silent** — the Apple TV is off, asleep, or on another network.
- **mDNS shows the device, 7000 closed** — likely a firewall on the Mac, or the TV dropped
  off Wi-Fi while staying in the cache.
- **No device in mDNS but the picker shows one** — multicast is filtered somewhere; that is
  a router setting, not something this tool can fix.
- **Nothing at all, guest network** — client isolation. Same story.

## What it does not do

- No packet capture and no changes to your network.
- Only TCP port checks; AirPlay also uses UDP and this tool does not probe it.
- mDNS discovery depends on 5353 being reachable from this machine, which is exactly what is
  broken in half the cases. Silence is a finding, not a bug in the tool.
- tvOS deep links are a different problem; see [atv-deeplink](https://github.com/hfip/atv-deeplink).

## بالعربي

<div dir="rtl" align="right">

مشاكل AirPlay غالباً مو من التطبيق، بل من الشبكة: الجهاز على شبكة ضيوف، أو الراوتر يحجب
الـ multicast، أو الـ Apple TV نايم.

```bash
airplay-doctor --device 10.0.0.42
```

يفحص: عناوين جهازك المحلية، منافذ AirPlay (7000/7001/5000)، وأجهزة mDNS اللي ترد. إذا
المنفذ مسكّر و mDNS ساكت، المشكلة في الشبكة أو الجهاز مو في التطبيق.

</div>

## License

MIT. See [LICENSE](LICENSE).
