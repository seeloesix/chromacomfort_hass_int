# ChromaComfort for Home Assistant

Local Bluetooth control of **Broan-NuTone ChromaComfort** bathroom exhaust fans.
No cloud, no vendor app, no account — Home Assistant talks straight to the fan
over BLE.

[![hacs][hacs-badge]][hacs]

## What you get

Each fan appears as one device with four entities:

| Entity | Type | Capabilities |
|---|---|---|
| Fan | `fan` | on / off (the unit is single-speed) |
| Light | `light` | on / off, brightness |
| Color light | `light` | on / off, brightness, RGB colour, **19 animated scenes** |
| Color cycle | `switch` | the fan's built-in colour sweep |

### Scenes

The colour light exposes animated scenes as Home Assistant **effects**, so you
can pick one from the light's more-info dialog or set it from an automation:

```yaml
service: light.turn_on
target:
  entity_id: light.chromacomfort_color_light
data:
  effect: Christmas
  brightness: 255
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

State is **pushed**, not polled: the fan streams its status several times a
second, so changes made at the wall switch or from the vendor app show up in
Home Assistant immediately.

The three light modes are mutually exclusive in the fan's own firmware — turning
on the colour light switches off the white light, and vice versa. The entities
reflect whatever the fan reports.

## Supported models

AER110RGBL, AERN110RGBL, SPK110RGBL, SPKN110RGBL, FG600RGB, FG800RGB, and the
Canadian `-C` variants. These are the models the official ChromaComfort app
lists. Any unit that advertises as `Chroma-Comfort` should work.

## Requirements

- Home Assistant 2024.8 or newer
- A Bluetooth adapter, or an [ESPHome Bluetooth proxy][proxy] within range of
  the fan

The fan needs no pairing or PIN, which means Bluetooth proxies work — useful
given bathroom fans are rarely near the Home Assistant host. (The PIN `1234` in
Broan's documentation is for the Sensonic speaker models' audio pairing, a
separate thing.)

## Installation

### HACS

1. In Home Assistant go to **HACS → ⋮ → Custom repositories**.
2. Add `https://github.com/seeloesix/chromacomfort` with type **Integration**.
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

**Entities show as unavailable.** That means the connection dropped or status
stopped arriving. The integration reconnects on its own every 10 seconds.

To report a problem, enable debug logging and include the output:

```yaml
logger:
  logs:
    custom_components.chromacomfort: debug
```

## Protocol

The wire protocol is documented in [PROTOCOL.md](PROTOCOL.md) — frame format,
opcodes, the status bitmask, the CRC algorithm, and the three non-obvious rules
you have to follow to make the fan listen. It is written to be useful to anyone
working with this hardware, not just to this integration.

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
[proxy]: https://esphome.io/components/bluetooth_proxy.html
