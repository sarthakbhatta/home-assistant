# Entity mapping — placeholders → your real devices

Every file in this kit uses the same ~22 placeholder entity IDs. Swap each for
your real entity once and everything — dashboard, automations, scripts — lines up.

**Find your real IDs:** Home Assistant → Developer Tools → States (filter by
domain, e.g. `light.`), or send me the output of this template
(Developer Tools → Template) and I'll do the renaming for you:

```jinja
{%- for s in states | rejectattr('domain','in',['automation','update','tts']) | sort(attribute='entity_id') %}
{{ s.entity_id }} | {{ s.attributes.friendly_name | default('') }} | {{ s.state }}
{%- endfor %}
```

## The map

| Placeholder | What it should be | Used in |
|---|---|---|
| `person.sarthak` | Your person entity | automations |
| `light.living_room_ceiling` | Main living room light | dashboard, automations, scripts |
| `light.living_room_lamp` | Living room floor/table lamp | dashboard, automations, scripts |
| `light.bedroom_ceiling` | Bedroom main light | dashboard |
| `light.bedroom_bedside` | Bedside lamp | dashboard, automations, scripts |
| `light.office_desk` | Office light | dashboard, scripts |
| `light.kitchen_main` | Kitchen light | dashboard, scripts |
| `light.hallway` | Hallway/entry light | automations |
| `climate.living_room_ac` | Living room AC/thermostat | dashboard, automations |
| `climate.bedroom_ac` | Bedroom AC/thermostat | dashboard, automations |
| `media_player.living_room_tv` | TV | dashboard, automations |
| `media_player.speakers` | Music speakers | dashboard, automations |
| `binary_sensor.front_door` | Front door contact sensor | dashboard, automations |
| `binary_sensor.living_room_window` | Living room window contact | automations |
| `binary_sensor.bedroom_window` | Bedroom window contact | automations |
| `binary_sensor.hallway_motion` | Hallway motion sensor | automations |
| `binary_sensor.kitchen_leak` | Leak sensor | automations |
| `sensor.living_room_temperature` | Living room temp sensor | dashboard |
| `sensor.bedroom_temperature` | Bedroom temp sensor | dashboard |
| `sensor.office_temperature` | Office temp sensor | dashboard |
| `sensor.bathroom_humidity` | Bathroom humidity sensor | dashboard, automations |
| `fan.bathroom_extractor` | Bathroom fan (or a smart plug `switch.`) | automations |
| `sensor.sarthak_phone_battery_level` | Companion app battery sensor | automations |
| `binary_sensor.sarthak_phone_is_charging` | Companion app charging sensor | automations |
| `notify.mobile_app_sarthak_phone` | Companion app notify service | automations |
| `weather.home` | Weather integration | automations |
| `calendar.personal` | Your calendar | automations |
| `event.bedside_button` | Optional Zigbee button | automations (commented) |

## Missing hardware?

No problem — the kit degrades gracefully:

- **No contact/motion/leak sensors yet:** skip `nc_midnight_path`,
  `nc_window_vs_climate`, `nc_door_ajar_nag`, `nc_night_watch`, `nc_leak_alarm`,
  and delete the "attention chip" conditional card from the dashboard.
  (A Zigbee dongle + a few Aqara sensors is the single best upgrade for this kit.)
- **No AC integration:** skip the climate automations and the Climate view.
- **Fewer rooms/lights:** delete the matching pop-up stack and chip-bar entry.

## Bulk rename (optional)

If you keep these files on disk, one placeholder can be renamed everywhere with:

```bash
grep -rl 'light.living_room_ceiling' . | xargs sed -i '' 's/light.living_room_ceiling/light.YOUR_REAL_ID/g'
```
