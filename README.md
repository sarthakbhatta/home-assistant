# Night Console — Home Assistant

The **Night Console** dashboard and automation suite is **installed and live**
on `http://sarthak.local:8123` → open **[Night Console](http://sarthak.local:8123/night-console/home)**
in the sidebar.

- **[DEPLOYED.md](DEPLOYED.md)** — exactly what's live: dashboard views,
  14 automations, scripts, helpers, theme, and every system change made
  (including the `configuration.yaml` fix that made automations load at all).
- **[themes/night-console.yaml](themes/night-console.yaml)** — reference copy
  of the deployed theme.
- **[archive/placeholder-kit/](archive/placeholder-kit/)** — the original
  generic kit drafted before device access (superseded; kept for reference).
- **[Idea board](https://claude.ai/code/artifact/60e40bae-f201-4ae0-9f14-da82c4e698d7)** —
  the three design directions; direction B (Night Console) is what was built.
  Direction C ("Flight Deck") is the planned phase-two wall-tablet dashboard.

Quick orientation: phone/desktop dashboard with a live status headline,
office-first controls, scene row (Focus · Wind down · All off), glass room
pop-ups (Office · Bedroom · Stairs · Living · Garden), an Energy view with
real power/kWh data, and an Admin view (batteries, updates, offline devices).
Automations arm a Night mode at 23:30, watch the terrace door and borewell
pump, pre-cool the office when you're heading home, and brief you on weekday
mornings.
