# ChromaComfort BLE protocol

Reverse-engineered notes for the Broan-NuTone ChromaComfort bath fan
(AER110RGBL, AERN110RGBL, SPK110RGBL, SPKN110RGBL, FG600RGB, FG800RGB and the
Canadian `-C` variants).

The radio is a **GooWi GWLE1010B** module — a **Qualcomm CSR1010** with a UART
host interface, FCC ID `2AFJJGWLE1010B`. The module relays framed packets
between its BLE GATT service and the fan's host MCU, which is why the protocol
carries its own start byte, length and checksum: that framing exists for the
serial link, not for GATT.

## GATT layout

Verified by enumeration against a live unit (firmware `20190311`):

```
service a08f7710-c37c-11e3-99cc-0228ac012a70          control service
  b34ae89e-c37c-11e3-940e-0228ac012a70  notify        status stream
  bb8a27e0-c37c-11e3-b953-0228ac012a70  write-no-rsp  commands
  bb8a27e1-c37c-11e3-b954-0228ac012a70  write-no-rsp, read
  00002a29  read  "GooWi Technology Co., Ltd."
  00002a28  read  "20190311"
  00002a00  read  "Chroma-Comfort"

service 00001016-d102-11e1-9b23-00025b00a5a5          DECOY - do not use
  00001013, 00001018, 00001014, 00001011
```

**The `00001016-…` service is the Qualcomm CSR over-the-air firmware update
service, not a control interface.** Its characteristics are readable and
writable and look inviting — `00001013` even reads back `01` — but writes to
them have no effect on the fan. Several earlier attempts at this device failed
by targeting it.

## Frame format

Every packet is 19 bytes in both directions.

```
[0]  0x3A  start of frame
[1]  0x11  length (17 bytes follow)
[2]  version    0x01 outbound, 0x05 inbound
[3]  control 1  0x00 outbound, 0xA0 inbound
[4]  control 2  0x40 command/ack, 0x41 status
...  payload
[18] trailer
```

### Commands (host → fan)

```
[0]=3A [1]=11 [2]=01 [3]=00 [4]=40 [5]=opcode
[6]=red [7]=green [8]=blue [9]=dimmer [10]=speed
[11]=sweep1 [12]=sweep2 [13]=duration [14..17]=timers [18]=trailer
```

| Field | Notes |
|---|---|
| `[2]` version | **Must be `0x01`.** The fan silently ignores commands carrying any other value, including the `0x05` it uses in its own replies. |
| `[6..8]` RGB | Raw 0–255, no gamma correction. |
| `[9]` dimmer | 0–100 percent. The fan clamps anything below 10 up to 10. |
| `[10]` speed | Zero on every command except `0x0D`, which uses 30. |
| `[11]`, `[12]` | Sweep colour defaults, `0x01` and `0x18`. |
| `[18]` trailer | Sent as `0x00`. The fan does not validate it on inbound commands. |

| Opcode | Action |
|---|---|
| `0x01` / `0x02` | Fan on / off |
| `0x03` / `0x04` | White light on / off (`dimmer` sets brightness) |
| `0x05` / `0x06` | Colour cycle on / off |
| `0x0B` / `0x0C` | Favourite colour on / off (`dimmer` sets brightness) |
| `0x0D` | Save favourite colour from `[6..8]`, with `speed = 30` |
| `0x11` / `0x12` | Countdown timer on / off |
| `0x20` / `0x21` / `0x2A` | Custom pattern activate / deactivate / save |

Setting a colour is two commands: `0x0D` to store it, then `0x0B` to activate.

### Gamma

Colours are **gamma-encoded with an exponent of 4** on all three channels before
transmission:

```
wire_value = floor((linear / 255) ** 4 * 255)
```

This applies to both the favourite colour (`0x0D`) and scene palettes. Skipping
it is easy to miss, because 0 and 255 are fixed points — pure primaries look
correct while every mixed colour comes out far too bright. Note how hard it
crushes midtones: 128 becomes 16, 200 becomes 96.

### Scenes / custom patterns

A scene is an animated palette of up to **8 colours** stored on the fan. The
device holds exactly one at a time, so switching scenes means re-uploading.

The palette is written as **two consecutive frames**. The first carries the
`0x2A` opcode and colour slots 0–3; the second has **no opcode at all** — byte 5
is colour data — and carries slots 4–7 plus the real palette length. Slot `k`
takes `colors[k % len]`, so short palettes repeat cyclically to fill all eight
while the fan learns the true loop length from the count byte.

```
frame 1:  [5] = 0x2A,  colours at bytes 6, 9, 12, 15   (slots 0-3)
frame 2:  no opcode,   colours at bytes 5, 8, 11, 14   (slots 4-7)
          [17] = number of colours (1-8)
```

Both frames keep the standard `3A 11 01 00 40` header. In frame 1 the colour
data overwrites the sweep bytes, so `sweep1`/`sweep2` carry no meaning during a
save.

Uploading and starting a scene is three steps, each separated by about a second:

1. `0x21` deactivate, with `dimmer = 10`.
2. The frame pair, written **as a pair, three times** — frame 1, frame 2, frame
   1, frame 2, and so on. Not each frame three times.
3. `0x20` activate, with `dimmer` = brightness and `speed` = cycle time in
   seconds (the app offers 30–240 in steps of 30).

A shorter gap than about a second before step 3 gets the activation dropped even
though the palette upload succeeded.

Activation sets status bit 1 (`0x02`). Sending `0x20` with an all-zero payload
is ignored outright, with no ACK.

The fan never reports which palette it holds, so a controller has to remember
what it uploaded.

#### The app's built-in scenes

Seven, taken verbatim from the app, all with a 30-second cycle:

| Scene | Colours |
|---|---|
| Sunset | `#FFD757` `#FF5A7C` `#7A9FFF` |
| Sunrise | `#FF5439` `#FF9E5C` `#FFE469` |
| Tropical Forest | `#86FD63` `#61F8FF` `#4B88FF` |
| Rainbow | `#B5B4FF` `#599CFF` `#8ED6FF` `#A3FF77` `#FCFF77` `#FFC671` `#FF6464` |
| Night Sky | `#9A76FF` `#EE80FF` `#A1CBFF` `#FFFFFF` |
| Underwater | `#FFFFFF` `#A6FBFF` `#679AFF` |
| Northern Lights | `#A6FF90` `#FDFB5D` `#FF7DD0` `#D177FF` |

Worked example — Sunrise, verified byte-for-byte against the app:

```
deactivate : 3A 11 01 00 40 21 00 00 00 0A 00 01 18 00 00 00 00 00 00
palette f1 : 3A 11 01 00 40 2A FF 03 00 FF 25 04 FF A2 07 FF 03 00 00
palette f2 : 3A 11 01 00 40 FF 25 04 FF A2 07 FF 03 00 FF 25 04 03 00
activate   : 3A 11 01 00 40 20 00 00 00 64 1E 01 18 00 00 00 00 00 00
```

### Status (fan → host)

```
[0]=3A [1]=11 [2]=05 [3]=A0 [4]=41 [5]=mask [6]=00 [7]=brightness ... [18]=CRC
```

Mask bits at `[5]`:

| Bit | Meaning |
|---|---|
| 7 (`0x80`) | Fan on |
| 6 (`0x40`) | White light on |
| 5 (`0x20`) | Colour cycle on |
| 4 (`0x10`) | RGB sweep |
| 3 (`0x08`) | Favourite colour 1 active |
| 2 (`0x04`) | Favourite colour 2 active |
| 1 (`0x02`) | User pattern active |

The light modes (bits 6, 5, 3) are mutually exclusive — turning one on clears
the others. The fan does **not** report its current RGB value, so a controller
has to remember what it last set.

Acknowledgements are short frames with control bytes `A0 40`.

### Checksum

Byte `[18]` of a status frame is **CRC-8/MAXIM** (Dallas/1-Wire: polynomial
`0x31` reflected to `0x8C`, init `0x00`, no final XOR) computed over bytes
`[1:18]` — the length byte through the last payload byte, excluding the `0x3A`
start byte.

This was recovered by brute-forcing the parameter space against 651 captured
status frames; it validates all 651 with no exceptions, and reproduces the
standard check value (`0xA1` for `"123456789"`). Those frames are checked in at
`tests/fixtures/captured_status_frames.json` and the test suite verifies every
one of them.

Use it to reject corrupt notifications. It is **not** required on outbound
commands — the fan does not check it, and sending `0x00` works fine.

## Talking to the fan

Three things are easy to get wrong and each fails in a way that looks like
something else:

1. **Subscribe before commanding.** The fan processes no commands at all until a
   client writes the status characteristic's CCCD. Then wait for the first
   status frame — commands sent between subscribing and the first notification
   are dropped.
2. **Write each frame three times, ~37 ms apart.** The command characteristic is
   write-without-response, so there is no BLE-level acknowledgement, and the fan
   drops isolated writes. The official app repeats every frame three times.
3. **Leave ~250 ms between two different commands.** The 37 ms gap is for
   repeats of one frame; back-to-back distinct commands cause the fan to act on
   only the first.

Even with all three, commands are occasionally lost. Since the fan reports
status several times a second, the reliable approach is to watch for the
expected state change and resend if it does not arrive — which is what this
integration does.

## One connection at a time

The fan accepts a **single Bluetooth connection**, and the vendor phone app wants
it too. Anything that holds the link permanently makes the app unusable: it will
still discover the fan, then hang forever on connect.

Worse, an automatic reconnect loop makes this permanent rather than transient —
it re-takes the connection within seconds of any release, so the app never gets a
window. If you are writing a controller for this device, connect on demand and
release promptly.

The advertisement carries only the fan's MAC address as manufacturer data under
company ID `0x000A` — **no state**. So there is no way to observe the fan
passively; state can only be read while connected. That is the fundamental
trade: state freshness costs the app its connection.

## No pairing required

The BLE control link is open: no pairing, no bonding, no passkey. The PIN
`1234` in the official documentation is for the **Sensonic speaker** models'
Bluetooth Classic A2DP audio pairing, which is a separate radio path.

This matters practically: because no bonding is involved, ESPHome Bluetooth
proxies work with this device.

## Credits

The command opcodes and the three delivery rules above were published by
[widowsson7/chromacomfort-ble-mqtt](https://github.com/widowsson7/chromacomfort-ble-mqtt),
building on [an earlier Bluetooth Classic implementation by taylorfinnell](https://gist.github.com/taylorfinnell/5349b8085d57836a45be7637055e0692).
The CRC algorithm, the GATT enumeration above and the decoy-service
identification are contributed by this project.
