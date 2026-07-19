# Night Console — Floor Plan (ha-floorplan proof of concept)

**Live at:** [Night Console → Plan](http://sarthak.local:8123/night-console/plan)

An interactive SVG floor plan of the office zone. Rooms and devices are drawn as
vector art; Home Assistant states drive CSS classes on the SVG, so the drawing
animates itself and is clickable.

## What it does

| Element | Behaviour |
|---|---|
| Office / Bath / Staircase lights (7) | Warm halo blooms with drop-shadow glow; **tap toggles the real light** |
| LED strip | Fills with an orange→amber gradient and blurs into a glow when on |
| Office AC | Unit outlines cyan, fan icon **spins continuously** while cooling |
| Workstation plug | Bolt turns green with a green border when powered |
| Borewell pump | Ring **pulses amber** and the icon glows while the motor runs |
| Terrace door | Door leaf **swings open ~74°** in red, with a dashed swing arc |
| Terrace motion | Amber core with two **expanding ripple rings** on motion |
| Garden valves | Droplets turn cyan and glow when a valve is open |
| Office temperature | Live number written into the plan (`text_set`) |

Sensors open more-info on tap; lights and switches toggle.

## Files

| Path | What |
|---|---|
| `office.source.svg` | Readable SVG source (art only, comments intact) — **edit this** |
| `office.source.css` | Readable CSS source (states + animations) — **edit this** |
| `office.deployed.svg` | Built artifact: minified SVG with the CSS inlined as `<style>` |
| `preview.html` | Standalone harness to preview the art without HA |

**On the HA box:** `/config/www/floorplan/office.svg` and `preview.html`,
served at `/local/floorplan/...`.

### Rebuilding after an edit

The deployed file is a single self-contained SVG (CSS embedded). To rebuild:
strip comments, minify the CSS, insert it as a `<style>` block before `<defs>`,
minify whitespace outside that block, then upload to
`/config/www/floorplan/office.svg`. Verify with `md5sum` against your local copy.

### Previewing without HA

Open `http://sarthak.local:8123/local/floorplan/preview.html` — the idle state.
Add `#on` (or run the class-injection snippet) to preview every animation at
once. This is the fast way to iterate on artwork before touching the dashboard.

## How the wiring works

ha-floorplan v1.1.5 injects the SVG into the DOM and matches rules to elements
by **exact `id` string comparison** — so SVG ids are literally entity ids
(`id="light.office_downlight_1"`). Dots are fine; ha-floorplan never uses a CSS
selector to find them.

Each rule's `state_action` calls `floorplan.class_set`, which **replaces the
whole class attribute** on the target element. That's why:

- structural classes live on **child** elements (`.halo`, `.ring`, `.bulb`) and
  the state class goes on the parent `<g>` — CSS then matches `.light-on .halo`;
- every `class_set` template re-emits the base class `floorplan-click`, so
  ha-floorplan's own click affordance isn't wiped.

### Two gotchas that cause a totally blank view

1. **`image:` must be a plain string path.** The object form
   `image: {location: ..., cache: false}` makes ha-floorplan v1.1.5 silently do
   nothing — it logs only "No stylesheet provided" and INIT, never fetches the
   SVG, and raises no error. Use `image: /local/floorplan/office_iso.svg`.
   (To bust caching after editing the SVG, append `?v=2` to the path.)
2. **The view needs an explicit `type: panel`.** Home Assistant 2026.7 no longer
   builds a view from legacy `panel: true` or the bare masonry default — the
   `hui-view` element is never created, so no card is instantiated at all.

Debugging tip: creating a `floorplan-card` element detached from the DOM always
reports blank, even with a known-good SVG — it's useless for bisecting. Test in
the real view, and add `log_level: debug` to the card to get its in-card log.

`log_level` was deliberately **removed**: it renders a visible white log panel
under the plan. Add it back temporarily when debugging rules.

The view is `panel: true` so the plan fills the width.

## Scope + next steps

This is a deliberate **proof of concept**: one floor, the well-instrumented
rooms (office, bath, staircase, terrace, garden). It is stylised — boxes and
icons, not an architectural drawing.

Options from here:

1. **Real geometry** — redraw to your actual room shapes and proportions (send a
   rough sketch or measurements, or trace a floor plan in Inkscape).
2. **Whole house** — add bedroom, living room, dining room; the bedroom WiZ
   lights and living-room media are already in HA.
3. **Richer interactions** — hold-to-dim, per-room hover tooltips with temp and
   power, camera thumbnail on the terrace, colour the room fill by temperature.
4. **Wall tablet** — this plan is the natural centrepiece of the "Flight Deck"
   tablet dashboard, with `kiosk-mode` hiding the HA chrome.
