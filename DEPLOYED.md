# Night Console — deployed state (2026-07-19)

Everything below is **live on your Home Assistant** (`http://sarthak.local:8123`,
HA OS 18.1, Core 2026.7.2). This file is the record of what was installed and
changed, so any future session (or you) can trace it.

## Dashboard

**[Night Console](http://sarthak.local:8123/night-console/home)** — new
storage-mode dashboard, in the sidebar with a moon icon. Your existing
Overview / Test / Minimalist dashboards were not touched.

| View | What's on it |
|---|---|
| **Home** | Live status headline (lights on · office temp · total watts · presence), conditional alert chips (terrace door open, borewell overheat/overload), Office AC hero, office light sliders, scene row (Focus · Wind down · All off), Dining TV, and a floating room chip bar |
| **Energy** | 24 h power graph (AC · workstation · laptop), office temp/humidity graph, borewell pump graph, today's + this-month's kWh tables |
| **Admin** | Night-mode toggle, device batteries, pending updates list, offline devices list |

Room chips open glass pop-ups: **Office** (4 lights, AC, meeting light,
workstation/laptop/coffee switches) · **Bedroom** (6 lights, 2 sockets) ·
**Stairs** (3 lights, borewell pump + its power graph) · **Living** (Samsung
TV, Jio box, VLC) · **Garden** (2 watering valves, terrace motion + door,
backside camera).

## Automations (all prefixed `NC ·`, ids `nc_*`, in `/config/automations.yaml`)

Starter: Sunset ambience · Welcome home · Empty-house sweep · Goodnight (23:30,
arms Night mode, phone-charge nag) · Morning briefing (weekdays 07:00).
Lighting: Late-night sweep (00:30).
Climate: Terrace door vs AC (pause + one-tap resume) · Hot office nudge
(>30° → actionable "Cool to 24°" notification) · AC notification actions ·
Pre-cool on approach (Near home zone + >29°).
Security: Terrace door ajar (nags ×3) · Night watch (staircase 100% + critical
alert) · Borewell guard (overheat/overload → pump off + critical alert) ·
Borewell runtime alert (45 min).

Notifications target `notify.mobile_app_sarthak_s_iphone`.

## Scripts / helpers / zone

- `script.office_focus`, `script.wind_down`, `script.everything_off`
- `input_boolean.night_mode` (armed by Goodnight, cleared by Morning briefing)
- `zone.near_home` (2.5 km radius around home, used by Pre-cool)

## System changes made

1. **HACS:** installed **Bubble Card v3.2.5** (mushroom + mini-graph-card were already present).
2. **`/config/configuration.yaml`:** appended the two missing include lines —
   ```yaml
   automation: !include automations.yaml
   script: !include scripts.yaml
   ```
   ⚠️ These were absent, which is why **no automation had ever loaded** on this
   instance. Backup saved at `/config/configuration.yaml.bak-nc`. Config was
   validated (`ha core check`) before the one core restart this required.
3. **Theme:** `/config/themes/night-console.yaml` (copy in [themes/night-console.yaml](themes/night-console.yaml)),
   set as your account's theme server-side (applies to the phone app too) and
   as the runtime default.
4. **Resurrected automations:** enabling the include also loaded 4 old drafts of
   yours ("Staircase Switch Automation", "Staircase Automation", "New
   automation", "New automation1") — all four are the same staircase-button →
   `light.staircase_bulb` toggle, and that entity no longer exists, so they do
   nothing. Safe to delete three (or all) in Settings → Automations, or point
   one at `light.st1/st2/st3`.

## Animation pass (2026-07-19, second session)

- **Power Flow Card Plus v0.3.7** (HACS) on the Energy view: animated
  moving-dot power flows — Mains → Home → AC / Workstation / Laptop /
  Borewell. Backed by a new template helper **`sensor.home_power`** (sum of
  the five Tuya power sensors, created via the Helpers UI, no YAML/restart).
  Note: the card requires at least one grid/solar/battery node — `home_power`
  is wired as the grid ("Mains") node.
- **Micro-animations** written into the Bubble cards' `styles` (no extra
  dependencies): press-squash + springy icon pop on every button (9 switches),
  a moving shine sweep across lit slider cards (16 sliders), the Office AC
  icon swapped to a **fan that spins while cooling** (2 climate cards), the
  borewell pump card **pulses amber + spins its icon while running**, alert
  chips pulse red, chip-bar buttons squash on press. All keyed off live state
  via Bubble's `${...}` JS templates; idempotent markers (`nc-*`) guard
  against double-application.

## Current state (end of 2026-07-19)

The dashboard has four views, all on **Bubble Card** with animations.

### The one bug behind every "blank dashboard" symptom

**A Lovelace view with no explicit `type:` does not render on HA 2026.7.2.**
The legacy masonry default — and legacy `panel: true` — silently fail: Home
Assistant creates the view *container* but never the view itself, so no card is
instantiated and the page looks blank. Every card inside then appears broken,
which is misleading.

**Always set `type:`** on every view. It also causes *partial, silent* failures:
the Admin view's "Updates" and "Offline devices" cards rendered as blank boxes
until its view was given a type — the templates behind them were fine all along.

Current view types: **home** `sections` · **energy** `masonry` ·
**admin** `masonry` · **plan** `panel`.

Bubble Card is *not* broken — buttons, sliders, separators, climate cards,
animated `styles` templates, pop-ups and the chip bar all work correctly once
the view has a type.

**Plan** is the isometric SmartThings-style floor plan (six 3D cutaway rooms).
Two settings are load-bearing — see [floorplan/README.md](floorplan/README.md):
the view needs `type: panel`, and the card's `image:` must be a **plain string**
path (the `{location, cache}` object form silently fails). The blue hub badges
were removed at the user's request.

## Room detail views (2026-07-19, fifth pass) — Office

Tapping the **OFFICE** pill on the Plan view now opens a dedicated
[Office room screen](http://sarthak.local:8123/night-console/office): the room
alone, rendered large enough to actually touch, with the lights, plugs and AC
tappable in the scene and a **CONTROLS** handle that shrinks the room to 44 %
and slides a tray of Bubble sliders up underneath it.

Design + rationale: [docs/superpowers/specs/2026-07-19-room-detail-views-design.md](docs/superpowers/specs/2026-07-19-room-detail-views-design.md).

Three things that are load-bearing and non-obvious:

1. **card-mod is NOT installed** on this instance (resources are only mushroom,
   mini-graph-card, Bubble-Card, power-flow-card-plus, ha-floorplan). Earlier
   notes here claiming otherwise were wrong. The drawer therefore resizes from
   **inside the SVG's own `<style>`**, which `gen_iso.py` generates — no new
   dependency.
2. **`height` rules on the SVG root need `!important`.** ha-floorplan writes
   inline `height:100%;width:100%` on the SVG and injects competing rules into
   the same shadow root. Without it the room overflows the view.
3. **The room's tap target is the label pill, not the room `<g>`.** Clicks
   bubble, so a ruled room group would fire both the light's rule and the
   room's on a single tap — toggling and navigating at once.

`gen_iso.py` now emits two files: `iso.svg` (overview, unchanged bytes) and
`room-office.svg` (one room, framed tightly by viewBox rather than redrawn).
Deployed as `/config/www/floorplan/office_iso.svg` and `room-office.svg`;
previous overview backed up at `office_iso.svg.bak-v2`.

## Floor plan (2026-07-19, fourth pass) — ha-floorplan proof of concept

New **Plan** view on the Night Console dashboard: an interactive SVG floor plan
of the office zone where lights glow in place, the AC fan spins, the terrace
door swings open, motion ripples, and the pump pulses — all driven by live
entity states, and clickable to control the real devices.

- Installed **ha-floorplan v1.1.5** via HACS.
- Artwork is a single self-contained SVG (CSS inlined) at
  `/config/www/floorplan/office.svg`, transferred and **md5-verified**.
- Full details, edit workflow and next steps: [floorplan/README.md](floorplan/README.md).
- Sources kept in [floorplan/](floorplan/); a standalone
  [preview harness](http://sarthak.local:8123/local/floorplan/preview.html)
  renders the art without Home Assistant.

## Lights & plugs reimagined (2026-07-19, third pass)

Research-driven rebuild of the two most-used card types (concepts from the
Bubble Card Module Store ecosystem — `icon_border_progress`, "Bubble Neon" —
and the Anashost animated-cards collection):

- **Light cards** now behave like light: the glow halo scales with brightness
  and takes the bulb's real color (`rgb_color`, else mapped from
  `color_temp_kelvin`, warm→cool); the icon has a lit radial core plus a
  **brightness progress ring**; the slider fill is an animated "liquid light"
  gradient with an ignite flash on turn-on. The LED strip additionally
  hue-rotates (rainbow) while on.
- **Plug cards** now behave like electricity: each powered switch
  (Workstation, Laptop, Coffee, Borewell) carries a **live wattage sub-button
  chip** (tap → power graph) and an **orbiting current-spark ring** around the
  icon whose speed scales with watts and whose color shifts green → amber →
  red (<60 W / <500 W / above). Borewell keeps its pulsing alert glow.
- All still pure Bubble `styles` templates (markers `nc-light`/`nc-plug`) —
  no extra dependencies.
- Gotcha for future edits: after saving dashboard config, **navigate via the
  UI**, not repeated forced URL loads — HA's view-transitions can wedge into a
  blank view (`InvalidStateError: Transition was aborted`); a tab click or
  fresh in-app navigation redraws it. The styles were not the problem.

## Fixes after first use

- **2026-07-19:** more-info dialogs (tapping a card's icon) rendered
  transparent, showing the dashboard through the dialog. Cause: dialogs
  inherit `card-background-color`, which this theme sets to 5.5% white glass.
  Fixed by adding opaque dialog/menu surface variables to the theme
  (`ha-dialog-surface-background`, `mdc-theme-surface`, input fill colors) —
  see the "Dialogs & menus" block in [themes/night-console.yaml](themes/night-console.yaml).

## Known notes

- **Bedroom WiZ lights + backside camera are `unavailable`** right now (likely
  powered off at the wall / offline). Their cards will grey out until they
  reconnect; the Admin view lists them.
- The AC target showed **18 °C** — the pop-up slider makes it easy to bump.
- On your phone: open the HA app → it will pick up the Night Console theme;
  set the default dashboard under app Settings → Companion app → General.
- **Best next hardware purchase:** one indoor motion sensor (hallway/stairs)
  unlocks midnight-path lighting; a couple of door/window sensors extend the
  security pack beyond the terrace door.

## Phase two (not yet built)

**Flight Deck** — the data-rich wall-tablet dashboard (direction C on the
[idea board](https://claude.ai/code/artifact/60e40bae-f201-4ae0-9f14-da82c4e698d7)):
ApexCharts temperature ribbons, energy areas, camera strip, kiosk-mode. Best
after a week or two of history data. The `archive/placeholder-kit/` folder
holds the original generic kit for reference.
