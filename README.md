<img src="custom_components/chromacomfort/brand/icon@2x.png" alt="ChromaComfort icon" width="128" align="right">

# ChromaComfort for Home Assistant

Local Bluetooth control of **Broan-NuTone ChromaComfort** bathroom exhaust fans.
No cloud, no vendor app, no account — Home Assistant talks straight to the fan
over BLE.

[![hacs][hacs-badge]][hacs]
[![release][release-badge]][releases]
[![license][license-badge]](LICENSE)

## What you get

Each fan appears as one device with five entities:

| Entity | Type | Capabilities |
|---|---|---|
| Fan | `fan` | on / off (the unit is single-speed) |
| Light | `light` | on / off, brightness |
| Color light | `light` | on / off, brightness, RGB colour, **19 animated scenes** |
| Scene | `select` | start or stop a scene straight from the device page |
| Color cycle | `switch` | the fan's built-in colour sweep |

### Scenes

Every scene's palette and cycle time is documented in
[docs/SCENES.md](docs/SCENES.md). The **Scene** select on the device page
starts one (or **Off** stops playback), and the colour light exposes the same
scenes as Home Assistant **effects**, so you can also pick one from the
light's more-info dialog or set it from an automation:

```yaml
service: light.turn_on
target:
  entity_id: light.chromacomfort_color_light
data:
  effect: Christmas
  brightness: 255
```

or, with the select:

```yaml
service: select.select_option
target:
  entity_id: select.chromacomfort_scene
data:
  option: Christmas
```

All seven of the vendor app's scenes are included — Sunset, Sunrise, Tropical
Forest, Rainbow, Night Sky, Underwater, Northern Lights — reproduced
byte-for-byte from the app. On top of those are twelve of our own: Christmas,
Halloween, Valentine, Independence Day, St. Patrick's Day, Easter, Thanksgiving,
Hanukkah, New Year, Mardi Gras, Candlelight, and Spa.

Scenes are uploaded to the fan on demand, so you are not limited to whatever the
app last stored. Adding your own is a few lines in `protocol.py` —
`EXTRA_SCENES` maps a name to a list of up to eight hex colours and a cycle time
in seconds. Bear in mind the fan gamma-encodes colours steeply, so saturated,
high-value channels read far better than pastels.

The three light modes are mutually exclusive in the fan's own firmware — turning
on the colour light switches off the white light, and vice versa. The entities
reflect whatever the fan reports.

## Sharing the fan with the phone app

The fan accepts **one Bluetooth connection at a time**. So this integration
connects only when it has something to do and releases about five seconds later,
which leaves the ChromaComfort app free to work in between.

What that means in practice:

- Home Assistant reads the fan's true state every time it sends a command, so
  after any action the state shown is correct.
- Between commands, Home Assistant shows the **last state it saw**. If you change
  something from the app or the wall switch, it will not notice until it next
  connects.
- To bound that staleness there is a periodic state refresh, **hourly by
  default**. Change it under the integration's **Configure** button — anywhere
  from every 5 minutes to never. Each refresh briefly takes the connection, so
  shorter intervals mean more chance of interrupting an app session.
- Entities stay **available** while disconnected, as long as the fan is still
  advertising.
- Changing a scene holds the connection for a few seconds — longer than other
  commands, because the palette upload is a multi-step sequence.

If the app is connected when Home Assistant tries to refresh, the refresh is
skipped silently and retried at the next interval.

## Supported models

AER110RGBL, AERN110RGBL, SPK110RGBL, SPKN110RGBL, FG600RGB, FG800RGB, and the
Canadian `-C` variants. These are the models the official ChromaComfort app
lists. Any unit that advertises as `Chroma-Comfort` should work.

## Requirements

- Home Assistant 2024.8 or newer (on 2026.3+ the device also shows the
  ChromaComfort icon, served from the integration's `brand/` directory)
- A Bluetooth adapter, or an [ESPHome Bluetooth proxy][proxy] within range of
  the fan

The fan needs no pairing or PIN, which means Bluetooth proxies work — useful
given bathroom fans are rarely near the Home Assistant host. (The PIN `1234` in
Broan's documentation is for the Sensonic speaker models' audio pairing, a
separate thing.)

## Installation

### HACS

1. In Home Assistant go to **HACS → ⋮ → Custom repositories**.
2. Add `https://github.com/seeloesix/chromacomfort_hass_int` with type **Integration**.
3. Find **ChromaComfort** in HACS and click **Download**.
4. Restart Home Assistant.

Updates then appear in HACS automatically whenever a new release is published.

### Manual

Copy `custom_components/chromacomfort/` into your Home Assistant
`config/custom_components/` directory and restart.

## Setup

Home Assistant discovers the fan automatically once it is in Bluetooth range —
look for a **ChromaComfort** discovery card on the Devices page and click
**Configure**.

To add one manually, go to **Settings → Devices & services → Add integration**
and search for **ChromaComfort**.

If you have several fans, each is a separate device keyed on its Bluetooth
address; add them one at a time.

## Troubleshooting

**The fan isn't discovered.** Confirm it has power, and that a Bluetooth adapter
or proxy is in range. Bathroom fans are often behind tile and joists, so signal
can be worse than the distance suggests — check the RSSI on the discovery card.

**Commands are ignored or slow.** The fan's command channel is
write-without-response and genuinely does drop packets. The integration resends
until the fan's own status confirms the change, so occasional retries are normal
and expected; a persistent failure usually means marginal signal.

**Entities show as unavailable.** Availability follows whether the fan is still
advertising, not whether Home Assistant holds a connection — it deliberately does
not, most of the time. So unavailable means the fan has gone out of range or lost
power. Entities that are available but showing stale values are a different
thing; see [Sharing the fan with the phone app](#sharing-the-fan-with-the-phone-app).

**"Could not reach &lt;fan&gt;" when running a command.** The fan takes one
connection at a time. If the ChromaComfort app is actively connected, Home
Assistant cannot reach the fan until the app disconnects. The command can
simply be retried once the app lets go.

**The Scene select shows nothing while colours are animating.** The fan never
reports *which* scene is loaded, only that one is playing. If playback was
started from the phone app rather than Home Assistant, the select honestly
shows unknown; picking any option takes over from there.

To report a problem, enable debug logging and include the output:

```yaml
logger:
  logs:
    custom_components.chromacomfort: debug
```

## Protocol and further documentation

- [PROTOCOL.md](PROTOCOL.md) — the wire protocol: frame format, opcodes, the
  status bitmask, the CRC algorithm, and the three non-obvious rules you have
  to follow to make the fan listen. Written to be useful to anyone working
  with this hardware, not just to this integration.
- [docs/SCENES.md](docs/SCENES.md) — every animated scene with its palette
  strip, hex colours, and cycle time.

Development tools live in `tools/`:

```bash
python tools/probe.py scan                    # find fans
python tools/probe.py dump   <address>        # enumerate GATT
python tools/probe.py watch  <address>        # decode the status stream
python tools/probe.py send   <address> fan_on # send commands
python tools/live_test.py    <address>        # end-to-end test against real hardware
```

Run the unit tests, which validate the protocol against 651 real captured
frames, with `pytest`.

## Credits

The command opcodes and the delivery rules were published by
[widowsson7/chromacomfort-ble-mqtt](https://github.com/widowsson7/chromacomfort-ble-mqtt),
building on [taylorfinnell's Bluetooth Classic
work](https://gist.github.com/taylorfinnell/5349b8085d57836a45be7637055e0692).

Not affiliated with or endorsed by Broan-NuTone. Licensed MIT.

[hacs]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[releases]: https://github.com/seeloesix/chromacomfort_hass_int/releases
[release-badge]: https://img.shields.io/github/v/release/seeloesix/chromacomfort_hass_int
[license-badge]: https://img.shields.io/github/license/seeloesix/chromacomfort_hass_int
[proxy]: https://esphome.io/components/bluetooth_proxy.html
