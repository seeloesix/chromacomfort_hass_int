# Animated scenes

The colour light plays animated scenes: the fan stores a palette of up to
eight colours and cross-fades through it over a fixed cycle time. The
integration exposes every scene below as an effect on the **Color light**
entity and as an option on the **Scene** select, and uploads the palette to
the fan on demand -- so you are never limited to whatever the vendor app
last loaded.

Colours are the linear `#RRGGBB` values before the fan's gamma-4 encoding
(see [PROTOCOL.md](../PROTOCOL.md) for the wire format). Palettes shorter
than eight slots repeat cyclically on the device.

Start a scene from an automation:

```yaml
service: light.turn_on
target:
  entity_id: light.chromacomfort_color_light
data:
  effect: Northern Lights
  brightness: 255
```

or with the select:

```yaml
service: select.select_option
target:
  entity_id: select.chromacomfort_scene
data:
  option: Northern Lights
```

## Vendor app scenes

Reproduced byte-for-byte from the ChromaComfort app.

| Scene | Palette | Colours | Cycle |
|---|---|---|---|
| Sunset | ![Sunset](scenes/sunset.png) | `#FFD757` `#FF5A7C` `#7A9FFF` | 30 s |
| Sunrise | ![Sunrise](scenes/sunrise.png) | `#FF5439` `#FF9E5C` `#FFE469` | 30 s |
| Tropical Forest | ![Tropical Forest](scenes/tropical-forest.png) | `#86FD63` `#61F8FF` `#4B88FF` | 30 s |
| Rainbow | ![Rainbow](scenes/rainbow.png) | `#B5B4FF` `#599CFF` `#8ED6FF` `#A3FF77` `#FCFF77` `#FFC671` `#FF6464` | 30 s |
| Night Sky | ![Night Sky](scenes/night-sky.png) | `#9A76FF` `#EE80FF` `#A1CBFF` `#FFFFFF` | 30 s |
| Underwater | ![Underwater](scenes/underwater.png) | `#FFFFFF` `#A6FBFF` `#679AFF` | 30 s |
| Northern Lights | ![Northern Lights](scenes/northern-lights.png) | `#A6FF90` `#FDFB5D` `#FF7DD0` `#D177FF` | 30 s |

## Additional scenes

Ours. Channels are kept high because the gamma-4 encoding crushes midtones
-- a channel at 128 lands at 16 on the wire -- so pastels would read as
near-black otherwise.

| Scene | Palette | Colours | Cycle |
|---|---|---|---|
| Christmas | ![Christmas](scenes/christmas.png) | `#FF1E1E` `#FFFFFF` `#1EFF46` | 30 s |
| Halloween | ![Halloween](scenes/halloween.png) | `#FF6A00` `#B026FF` `#4CFF29` | 30 s |
| Valentine | ![Valentine](scenes/valentine.png) | `#FF0A46` `#FF6FA5` `#FFB3C9` | 30 s |
| Independence Day | ![Independence Day](scenes/independence-day.png) | `#FF1E1E` `#FFFFFF` `#2E5CFF` | 30 s |
| St. Patrick's Day | ![St. Patrick's Day](scenes/st-patrick-s-day.png) | `#00D64F` `#7CFF52` `#FFD700` | 30 s |
| Easter | ![Easter](scenes/easter.png) | `#FFAFCF` `#AEE7FF` `#FFF48F` `#B6FFC0` | 60 s |
| Thanksgiving | ![Thanksgiving](scenes/thanksgiving.png) | `#FF4E11` `#FF8C1A` `#FFC04D` `#FFE79E` | 60 s |
| Hanukkah | ![Hanukkah](scenes/hanukkah.png) | `#2E6CFF` `#8FC2FF` `#FFFFFF` | 30 s |
| New Year | ![New Year](scenes/new-year.png) | `#FFD700` `#FFFFFF` `#FFF2A8` | 30 s |
| Mardi Gras | ![Mardi Gras](scenes/mardi-gras.png) | `#8A1FFF` `#00C74D` `#FFD700` | 30 s |
| Candlelight | ![Candlelight](scenes/candlelight.png) | `#FF8A1E` `#FFB347` `#FFD79A` | 240 s |
| Spa | ![Spa](scenes/spa.png) | `#8CFFD6` `#B7F3FF` `#E8FFFA` | 240 s |
