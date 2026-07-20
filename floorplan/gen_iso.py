#!/usr/bin/env python3
"""Generate a SmartThings-style isometric 3D floorplan SVG for Home Assistant / ha-floorplan."""
import math, re, hashlib, base64

COS30 = math.cos(math.radians(30))
SIN30 = 0.5
U = 15.0                      # px per world unit
ELL_RX = COS30 * math.sqrt(2) # ground circle -> ellipse semi-axes
ELL_RY = SIN30 * math.sqrt(2)

# face shading multipliers
F_TOP, F_RIGHT, F_LEFT = 1.0, 0.80, 0.62


def iso(x, y, z=0.0):
    return ((x - y) * COS30 * U, (x + y) * SIN30 * U - z * U)


def pts(cs):
    return " ".join("%.1f,%.1f" % (a, b) for a, b in cs)


def shade(c, f):
    c = c.lstrip('#')
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    cl = lambda v: max(0, min(255, int(round(v * f))))
    return "#%02X%02X%02X" % (cl(r), cl(g), cl(b))


class Room:
    def __init__(self, key, name, pos, W, D, H, wall, floor, base_id=None):
        self.key, self.name, self.pos = key, name, pos
        self.W, self.D, self.H = W, D, H
        self.wall, self.floor = wall, floor
        self.items = []      # (sortkey, svg)
        self.overlay = []    # drawn last (labels, glows)

    def add(self, sort, svg):
        self.items.append((sort, svg))

    # ---------- primitives ----------
    def box(self, x, y, z, w, d, h, color, cls="", eid="", sort=None):
        top = [iso(x, y, z + h), iso(x + w, y, z + h), iso(x + w, y + d, z + h), iso(x, y + d, z + h)]
        rgt = [iso(x + w, y, z), iso(x + w, y + d, z), iso(x + w, y + d, z + h), iso(x + w, y, z + h)]
        lft = [iso(x, y + d, z), iso(x + w, y + d, z), iso(x + w, y + d, z + h), iso(x, y + d, z + h)]
        g = ('<g%s%s>' % (' id="%s"' % eid if eid else '', ' class="%s"' % cls if cls else '')
             + '<polygon class="f-l" points="%s" fill="%s"/>' % (pts(lft), shade(color, F_LEFT))
             + '<polygon class="f-r" points="%s" fill="%s"/>' % (pts(rgt), shade(color, F_RIGHT))
             + '<polygon class="f-t" points="%s" fill="%s" stroke="%s" stroke-width="0.7"/>'
             % (pts(top), shade(color, F_TOP), shade(color, 1.18))
             + '</g>')
        self.add(sort if sort is not None else (x + y + z * 0.5), g)
        return g

    def plate(self, x, y, z, w, d, color, cls="", eid=""):
        """flat horizontal panel (rug, screen glow on floor)"""
        p = [iso(x, y, z), iso(x + w, y, z), iso(x + w, y + d, z), iso(x, y + d, z)]
        self.add(x + y - 0.01, '<polygon%s%s points="%s" fill="%s"/>' % (
            ' id="%s"' % eid if eid else '', ' class="%s"' % cls if cls else '', pts(p), color))

    def pool(self, cx, cy, r, cls, eid, sort=None, z_top=None, apex=None):
        """Ground light pool, optionally with a visible beam down from the ceiling.

        Wrapped in a <g> carrying the entity id so a single class_set lights the
        pool AND the cone together. The cone is what makes a ceiling light
        findable: the floor pool alone reads as a smudge and gives no clue
        where the fixture you need to tap actually is.
        """
        px, py = iso(cx, cy, 0)
        rx, ry = r * ELL_RX * U, r * ELL_RY * U
        inner = ''
        if z_top is not None:
            # apex lets the beam slant: the fixture sits at `apex` while the
            # pool lands at (cx, cy), so light arrives at an angle rather than
            # dropping straight down.
            ax, ay = apex if apex else (cx, cy)
            tx, ty = iso(ax, ay, z_top)
            inner += ('<path class="beam" d="M%.1f %.1f L%.1f %.1f A%.1f %.1f 0 0 0 %.1f %.1f Z"/>'
                      % (tx, ty, px - rx, py, rx, ry, px + rx, py))
        inner += ('<ellipse class="poolel" cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f"/>'
                  % (px, py, rx, ry))
        self.add(sort if sort is not None else (cx + cy - 0.02),
                 '<g class="%s" id="%s">%s</g>' % (cls, eid, inner))

    def dot(self, x, y, z, r, cls, eid="", sort=None):
        px, py = iso(x, y, z)
        self.add(sort if sort is not None else (x + y + z * 0.5),
                 '<circle%s class="%s" cx="%.1f" cy="%.1f" r="%.1f"/>' % (
                     ' id="%s"' % eid if eid else '', cls, px, py, r))

    def face_circle(self, x, y, z, r, fill, stroke="", sw=0.0):
        """Circle lying in a constant-y plane (a front panel), not screen-flat.

        In that plane +x projects to (cos30, sin30) and +z straight up, so the
        matrix skews a plain circle onto the face. Needed for dials and gauges:
        drawn screen-flat they look like stickers floating in front of the box.
        """
        tx, ty = iso(x, y, z)
        extra = ' stroke="%s" stroke-width="%.2f"' % (stroke, sw) if stroke else ''
        self.add(x + y + z * 0.5 + 0.02,
                 '<g transform="matrix(%.4f %.4f 0 1 %.1f %.1f)">'
                 '<circle cx="0" cy="0" r="%.1f" fill="%s"%s/></g>'
                 % (COS30, SIN30, tx, ty, r * U, fill, extra))

    def shadow(self, cx, cy, rx, ry=None, op=0.34):
        """Soft contact shadow where an object meets the floor.

        The single strongest cue that something is *sitting* in the room rather
        than pasted onto it. Sorted just under the object it belongs to.
        """
        px, py = iso(cx, cy, 0)
        ry = ry if ry is not None else rx
        self.add(cx + cy - 0.04,
                 '<ellipse class="contact" cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" '
                 'style="opacity:%.2f"/>'
                 % (px, py + 2, rx * ELL_RX * U, ry * ELL_RY * U, op))

    def wedge(self, x, y, z, w, d, h0, h1, color, cls="", eid="", sort=None):
        """Box with a sloped top -- h0 at the y edge ramping to h1 at y+d.

        Everything in the room was a right prism before this; nothing could
        lean. Laptop lids, monitor tilt and desk ramps all need it.
        """
        top = [iso(x, y, z + h0), iso(x + w, y, z + h0),
               iso(x + w, y + d, z + h1), iso(x, y + d, z + h1)]
        rgt = [iso(x + w, y, z), iso(x + w, y + d, z),
               iso(x + w, y + d, z + h1), iso(x + w, y, z + h0)]
        lft = [iso(x, y + d, z), iso(x + w, y + d, z),
               iso(x + w, y + d, z + h1), iso(x, y + d, z + h1)]
        g = ('<g%s%s>' % (' id="%s"' % eid if eid else '', ' class="%s"' % cls if cls else '')
             + '<polygon class="f-l" points="%s" fill="%s"/>' % (pts(lft), shade(color, F_LEFT))
             + '<polygon class="f-r" points="%s" fill="%s"/>' % (pts(rgt), shade(color, F_RIGHT))
             + '<polygon class="f-t" points="%s" fill="%s" stroke="%s" stroke-width="0.7"/>'
             % (pts(top), shade(color, F_TOP), shade(color, 1.18))
             + '</g>')
        self.add(sort if sort is not None else (x + y + z * 0.5), g)

    def raw_box(self, x, y, z, w, d, h, color):
        """The three faces of a box as a bare SVG string -- not added to the room.

        Lets a single device be composed from several parts inside one <g>, so
        a state class (plug-on, light-on) still lights the whole object at once.
        """
        top = [iso(x, y, z + h), iso(x + w, y, z + h), iso(x + w, y + d, z + h), iso(x, y + d, z + h)]
        rgt = [iso(x + w, y, z), iso(x + w, y + d, z), iso(x + w, y + d, z + h), iso(x + w, y, z + h)]
        lft = [iso(x, y + d, z), iso(x + w, y + d, z), iso(x + w, y + d, z + h), iso(x, y + d, z + h)]
        return ('<polygon class="f-l" points="%s" fill="%s"/>' % (pts(lft), shade(color, F_LEFT))
                + '<polygon class="f-r" points="%s" fill="%s"/>' % (pts(rgt), shade(color, F_RIGHT))
                + '<polygon class="f-t" points="%s" fill="%s" stroke="%s" stroke-width="0.7"/>'
                % (pts(top), shade(color, F_TOP), shade(color, 1.18)))

    def cyl(self, cx, cy, z0, z1, r, color, cls="", eid="", sort=None):
        """Upright cylinder. The primitive that makes things stop looking like boxes.

        A circle on the ground plane projects to an axis-aligned ellipse with
        rx = r*cos30*sqrt2, ry = r*sin30*sqrt2 (same relationship pool() uses).
        Body is the quad between the two ellipses' horizontal extremes, with the
        bottom ellipse drawn behind it so the base reads as round.
        """
        bx, by = iso(cx, cy, z0)
        tx, ty = iso(cx, cy, z1)
        rx, ry = r * ELL_RX * U, r * ELL_RY * U
        s = ('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s"/>'
             % (bx, by, rx, ry, shade(color, F_LEFT))
             + '<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="%s"/>'
             % (bx - rx, by, bx + rx, by, tx + rx, ty, tx - rx, ty, shade(color, F_RIGHT))
             + '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s"/>'
             % (tx, ty, rx, ry, shade(color, F_TOP)))
        self.add(sort if sort is not None else (cx + cy + z0 * 0.5),
                 '<g%s%s>%s</g>' % (' id="%s"' % eid if eid else '',
                                    ' class="%s"' % cls if cls else '', s))

    def wall_text(self, y, z, text, cls="metric", eid="", size=None):
        """Text lying flat ON the near (x=W) wall, not floating in screen space.

        The wall's +y direction projects to (-cos30, +sin30) and +z to (0,-1),
        so skewing the glyphs by that basis makes them sit in the wall plane.
        Runs along -y so it reads left-to-right on screen.
        """
        tx, ty = iso(self.W + 0.04, y, z)
        self.overlay.append(
            '<text%s class="%s"%s transform="matrix(%.4f %.4f 0 1 %.1f %.1f)" x="0" y="0">%s</text>'
            % (' id="%s"' % eid if eid else '', cls,
               ' style="font-size:%dpx"' % size if size else '',
               COS30, -SIN30, tx, ty, text))

    def panel(self, wall, a, b, z0, z1, color, cls="", eid=""):
        """Flat panel set into a visible wall -- doors, windows, wall art.

        wall='back' lies in the y=0 plane and spans x from a to b;
        wall='left' lies in the x=0 plane and spans y from a to b.
        """
        off = 0.03                         # float just proud of the wall face
        if wall == 'back':
            p = [iso(a, off, z0), iso(b, off, z0), iso(b, off, z1), iso(a, off, z1)]
            sort = a + off
        else:
            p = [iso(off, a, z0), iso(off, b, z0), iso(off, b, z1), iso(off, a, z1)]
            sort = off + a
        self.add(sort, '<polygon%s%s points="%s" fill="%s"/>' % (
            ' id="%s"' % eid if eid else '', ' class="%s"' % cls if cls else '',
            pts(p), color))

    def stub(self, a, b, h, color):
        """A fragment of the near (x=W) wall, which is otherwise cut away.

        Wall-mounted kit on the cut-away side would otherwise float in space.
        Drawing just the slice it occupies reads as a deliberate cutaway rather
        than a mistake, and keeps the layout honest instead of relocating the
        device to a wall it is not actually on.
        """
        W, t = self.W, 0.3
        face = [iso(W, a, 0), iso(W, b, 0), iso(W, b, h), iso(W, a, h)]
        cap = [iso(W, a, h), iso(W, b, h), iso(W + t, b, h), iso(W + t, a, h)]
        edge = [iso(W, b, 0), iso(W + t, b, 0), iso(W + t, b, h), iso(W, b, h)]
        self.add(W + a - 0.4,
                 '<polygon points="%s" fill="%s"/>' % (pts(face), shade(color, 0.62))
                 + '<polygon points="%s" fill="%s"/>' % (pts(cap), shade(color, 1.02))
                 + '<polygon points="%s" fill="%s"/>' % (pts(edge), shade(color, 0.5)))

    # ---------- shell ----------
    def shell(self):
        W, D, H, wall, floor = self.W, self.D, self.H, self.wall, self.floor
        t = 0.35   # wall thickness
        s = []
        # floor
        s.append('<polygon points="%s" fill="%s"/>' % (
            pts([iso(0, 0), iso(W, 0), iso(W, D), iso(0, D)]), floor))
        # right wall (y=0 plane), faces +y viewer -> use F_RIGHT tone
        s.append('<polygon points="%s" fill="%s"/>' % (
            pts([iso(0, 0, 0), iso(W, 0, 0), iso(W, 0, H), iso(0, 0, H)]), shade(wall, 0.86)))
        # left wall (x=0 plane)
        s.append('<polygon points="%s" fill="%s"/>' % (
            pts([iso(0, 0, 0), iso(0, D, 0), iso(0, D, H), iso(0, 0, H)]), shade(wall, 0.62)))
        # wall thickness caps
        s.append('<polygon points="%s" fill="%s"/>' % (
            pts([iso(0, 0, H), iso(W, 0, H), iso(W, -t, H), iso(0, -t, H)]), shade(wall, 1.06)))
        s.append('<polygon points="%s" fill="%s"/>' % (
            pts([iso(0, 0, H), iso(0, D, H), iso(-t, D, H), iso(-t, 0, H)]), shade(wall, 0.98)))
        # outer thin edges
        s.append('<polygon points="%s" fill="%s"/>' % (
            pts([iso(W, 0, 0), iso(W, -t, 0), iso(W, -t, H), iso(W, 0, H)]), shade(wall, 0.70)))
        s.append('<polygon points="%s" fill="%s"/>' % (
            pts([iso(0, D, 0), iso(-t, D, 0), iso(-t, D, H), iso(0, D, H)]), shade(wall, 0.52)))
        # floor front edges (slab thickness)
        fd = 0.45
        s.append('<polygon points="%s" fill="%s"/>' % (
            pts([iso(W, 0, 0), iso(W, D, 0), iso(W, D, -fd), iso(W, 0, -fd)]), shade(floor, 0.72)))
        s.append('<polygon points="%s" fill="%s"/>' % (
            pts([iso(0, D, 0), iso(W, D, 0), iso(W, D, -fd), iso(0, D, -fd)]), shade(floor, 0.55)))
        return "".join(s)

    def render(self):
        body = self.shell()
        for _, svg in sorted(self.items, key=lambda kv: kv[0]):
            body += svg
        body += "".join(self.overlay)
        # soft ground shadow
        sx, sy = iso(self.W / 2.0, self.D / 2.0, 0)
        shadow = '<ellipse class="room-shadow" cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f"/>' % (
            sx, sy + 14, (self.W + self.D) * COS30 * U * 0.52, (self.W + self.D) * SIN30 * U * 0.42)
        return '<g class="room" transform="translate(%.1f,%.1f)">%s%s</g>' % (
            self.pos[0], self.pos[1], shadow, body)

    def label(self):
        """Room name pill. Doubles as the tap target for entering the room.

        The pill carries the id rather than the room <g> on purpose: clicks
        bubble, so a tap on a light inside a ruled room group would fire both
        the light's rule and the room's, toggling and navigating at once.
        The pill never overlaps a device, so it cannot collide.
        """
        cx, cy = iso(self.W * 0.62, self.D * 0.95, 0)
        cx += self.pos[0]; cy += self.pos[1] + 34
        w = 20 + len(self.name) * 9.2
        return ('<g id="room-%s" class="pill">'
                '<rect x="%.1f" y="%.1f" width="%.1f" height="30" rx="15"/>'
                '<text x="%.1f" y="%.1f">%s</text></g>') % (
            self.key, cx - w / 2, cy - 15, w, cx, cy + 5.5, self.name)

    def badge(self, eid, nav):
        """floating hub badge, taps through to the room pop-up"""
        cx, cy = iso(self.W * 0.46, self.D * 0.18, self.H * 1.02)
        cx += self.pos[0]; cy += self.pos[1]
        return ('<g id="%s" class="badge" data-nav="%s">'
                '<circle class="badge-ring" cx="%.1f" cy="%.1f" r="22"/>'
                '<circle class="badge-core" cx="%.1f" cy="%.1f" r="15"/>'
                '<circle class="badge-hub" cx="%.1f" cy="%.1f" r="3.2"/>'
                '<circle class="badge-hub" cx="%.1f" cy="%.1f" r="2.4"/>'
                '<circle class="badge-hub" cx="%.1f" cy="%.1f" r="2.4"/>'
                '<circle class="badge-hub" cx="%.1f" cy="%.1f" r="2.4"/>'
                '<circle class="badge-hub" cx="%.1f" cy="%.1f" r="2.4"/>'
                '</g>') % (eid, nav, cx, cy, cx, cy, cx, cy,
                           cx - 7, cy - 5, cx + 7, cy - 5, cx - 7, cy + 5, cx + 7, cy + 5)


def plant(rm, x, y, pot="#B9744A", leaf="#4CAF7D", s=1.0):
    rm.box(x, y, 0, 0.9 * s, 0.9 * s, 0.7 * s, pot)
    px, py = iso(x + 0.45 * s, y + 0.45 * s, 0.7 * s)
    rm.add(x + y + 0.4,
           '<g class="leaf"><ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s"/>'
           '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s"/>'
           '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s"/></g>' % (
               px, py - 10 * s, 9 * s, 12 * s, leaf,
               px - 9 * s, py - 4 * s, 7 * s, 9 * s, shade(leaf, 0.82),
               px + 9 * s, py - 5 * s, 7 * s, 9 * s, shade(leaf, 0.92)))


# =====================================================================
# ROOMS
# =====================================================================
ROOMS = []

# ---------------------------------------------------------------- OFFICE
o = Room('office', 'OFFICE', (190, 195), 11, 9, 5.2, '#2FBFAE', '#5FC9B8')
# --- Layout from the user's drag-and-drop planner (2026-07-19), MIRRORED in x.
# The planner put the desk/monitor/strip on the x=W wall, which is cut away in
# the isometric view -- they would have floated at the open edge. Mirroring
# (x' = W - x - w) puts that cluster on the visible x=0 wall. The AC was on the
# opposite wall and therefore had to become the hidden one; it gets a wall stub.
# v3 cleanup: monitor, cabinet, plant, printer and rug were deleted on purpose.
# desk down the left wall (planner x=8.5 -> 0.6)
o.shadow(1.55, 4.6, 1.35, 2.9, op=0.40)
o.box(0.6, 2.0, 0, 1.9, 5.2, 1.5, '#F2F5F7')                       # desk top
o.box(0.68, 2.08, 0, 0.16, 0.16, 1.5, '#C7CFD7')                   # desk legs
o.box(2.26, 2.08, 0, 0.16, 0.16, 1.5, '#C7CFD7')
o.box(0.68, 7.04, 0, 0.16, 0.16, 1.5, '#C7CFD7')
o.box(2.26, 7.04, 0, 0.16, 0.16, 1.5, '#C7CFD7')
# office chair removed on request -- it sat right where the downlight pools
# land, and cutting it opens the floor so the light actually reads.
# workstation tower, under the desk against the wall (planner x=9 -> 0.8)
o.box(0.80, 5.5, 0, 1.2, 1.4, 1.42, '#5B6674', eid='switch.office_main_desk', cls='plug')
o.add(9.3, '<polygon class="bolt" id="switch.office_main_desk-bolt" points="%s"/>' % pts([
    iso(2.00, 5.95, 1.15), iso(2.00, 6.18, 0.72), iso(2.00, 6.06, 0.72),
    iso(2.00, 6.26, 0.3), iso(2.00, 5.82, 0.92), iso(2.00, 5.98, 0.92)]))
# laptop on the desk -- lid uses the new wedge so it actually leans back
o.box(0.85, 2.1, 1.5, 1.35, 1.8, 0.10, '#E4E9EE')                  # keyboard deck
o.wedge(0.88, 2.14, 1.60, 0.22, 1.70, 0.95, 1.15, '#2C3440',
        eid='switch.laptop_office', cls='plug')                    # lid, tilted
# espresso machine, modelled on the reference: dark plinth, chrome drip tray,
# rear body column, overhanging head with a control panel, portafilter + cup.
# All one <g> so plug-on still lights the whole appliance at once.
# Rotated 180 deg about its own centre (y=7.06). The visible face in this
# projection is the HIGH-y one, so the control panel, group head, portafilter
# and cup all have to live at high y -- built the other way round they end up
# on the side facing away from the viewer, which is what happened first time.
o.shadow(7.56, 7.06, 0.85, 0.85, op=0.40)
BODY, PANEL, DARK, CHROME = '#E08A5C', '#EDA47C', '#7A4630', '#D8DDE1'
o.add(6.85 + 6.35, '<g id="switch.coffee_machine_switch" class="plug">'
      + o.raw_box(6.85, 6.35, 0.00, 1.42, 1.42, 0.26, DARK)           # plinth
      + o.raw_box(6.93, 6.67, 0.26, 1.26, 1.02, 0.07, CHROME)         # drip tray
      + o.raw_box(6.90, 6.39, 0.26, 1.32, 0.68, 1.44, BODY)           # body column (rear)
      + o.raw_box(6.85, 6.39, 1.44, 1.42, 1.15, 0.70, PANEL)          # head, overhangs forward
      + o.raw_box(6.90, 7.50, 1.36, 1.32, 0.10, 0.20, DARK)           # head front lip
      + o.raw_box(7.28, 7.20, 1.10, 0.34, 0.30, 0.28, '#2B2320')      # group head
      + o.raw_box(7.34, 7.46, 1.16, 0.20, 0.26, 0.14, '#7A4630')      # portafilter handle
      + '</g>')
# control panel on the head's forward face -- layered toward the viewer, so
# each element sits at a slightly HIGHER y than the one behind it
o.face_circle(7.35, 7.55, 1.86, 0.20, '#2B2320')                      # gauge bezel
o.face_circle(7.35, 7.56, 1.86, 0.13, '#E8B48F')                      # gauge face
o.face_circle(7.35, 7.57, 1.86, 0.05, '#2B2320')                      # needle hub
for _bx, _bz in ((7.66, 1.94), (7.66, 1.74), (7.04, 1.94), (7.04, 1.74)):
    _px, _py = iso(_bx, 7.56, _bz)
    o.add(_bx + 7.56 + _bz * 0.5 + 0.02,
          '<g transform="matrix(%.4f %.4f 0 1 %.1f %.1f)">'
          '<rect x="-3.4" y="-2.0" width="6.8" height="4.0" rx="2" fill="#D8DDE1"/></g>'
          % (COS30, SIN30, _px, _py))
o.cyl(8.34, 7.17, 1.62, 1.78, 0.17, CHROME)                           # side knob
o.cyl(7.45, 7.35, 0.33, 0.72, 0.22, '#241E1B')                        # cup under the spout
o.cyl(7.45, 7.35, 0.70, 0.73, 0.19, '#4A342A')                        # coffee surface
# standing bar lamp = switch.office_office_meeting_light (planner x=9 -> 0.5).
# A switch, not a light: it can glow but it cannot dim.
o.shadow(1.25, 7.75, 0.66, 0.66, op=0.42)
o.pool(1.25, 7.75, 1.7, 'pool', 'switch.office_office_meeting_light-pool', sort=-45)
o.cyl(1.25, 7.75, 0.0, 0.14, 0.52, '#39424D')                         # weighted base
o.cyl(1.25, 7.75, 0.14, 0.55, 0.09, '#5D6874')                        # stem
o.box(1.16, 7.66, 0.55, 0.18, 0.18, 3.45, '#E8ECF0',
      eid='switch.office_office_meeting_light', cls='bar')            # the bar itself
o.box(1.12, 7.62, 4.00, 0.26, 0.26, 0.12, '#39424D')                  # top cap
# TV -- furniture only for now: there is no "office TV" entity in HA, so it
# carries no id and no tap action. Bind it once the right media_player is known.
o.box(4.4, 0.06, 2.4, 2.6, 0.28, 1.5, '#2C3440')
o.add(3.6, '<polygon class="screen" points="%s" fill="#171C24"/>' % pts([
    iso(4.55, 0.36, 2.55), iso(6.85, 0.36, 2.55), iso(6.85, 0.36, 3.75), iso(4.55, 0.36, 3.75)]))
# door in the back wall (planner x=1 -> 8.8)
o.panel('back', 8.8, 10.0, 0, 3.4, '#6B4A38')
o.panel('back', 8.9, 9.9, 0.1, 3.3, '#7D5943')
# wall AC -- really on the cut-away side, so it gets a fragment of wall to hang on
o.stub(2.6, 6.9, 4.9, '#2FBFAE')
o.box(10.45, 3.0, 3.5, 0.55, 3.4, 1.1, '#F4F7F9',
      eid='climate.panasonic_ac_panasonic_ac', cls='ac')
_ax, _ay = iso(10.7, 4.7, 4.05)
o.add(99, '<g class="fan" id="climate.panasonic_ac_panasonic_ac-fan" style="transform-origin:%.1fpx %.1fpx"><circle class="fan-ring" cx="%.1f" cy="%.1f" r="9"/>'
          '<path class="fan-b" d="M%.1f %.1f q6 -3 0 -9 q-6 6 0 9z"/>'
          '<path class="fan-b" d="M%.1f %.1f q-6.5 -1.5 -7 6 q8 0.5 7 -6z"/>'
          '<path class="fan-b" d="M%.1f %.1f q6.5 -1.5 7 6 q-8 0.5 -7 -6z"/></g>' % (
              _ax, _ay, _ax, _ay, _ax, _ay, _ax, _ay, _ax, _ay))
# LED strip high on the left wall (planner x=10.5 -> 0.25)
o.box(0.05, 1.5, 4.2, 0.18, 6.4, 0.28, '#FFFFFF', eid='light.smart_light_strip1', cls='strip')
# ceiling downlights -- planner centres, mirrored
# Downlights: the fixture stays on the ceiling but the pool is thrown forward
# and to the right, so the beam slants across the room instead of dropping
# straight down. Pools widened 2.3 -> 3.3 so the light reads at room scale.
for i, (lx, ly, ent) in enumerate([(6.75, 4.25, 'light.office_downlight_1'),
                                   (4.75, 4.25, 'light.office_downlight_2')]):
    px, py = lx - 1.5, ly + 1.9                     # where the pool lands
    o.pool(px, py, 3.3, 'pool', ent + '-pool', sort=-50 + i, z_top=4.9, apex=(lx, ly))
    o.dot(lx, ly, 4.9, 6.4, 'fixture', ent, sort=200 + i)
# bathroom: a LOW partition across the front (planner x=3.5 -> 3.1, y=8).
# Kept short on purpose -- at full height it stands between you and the room.
o.box(3.1, 8.0, 0, 4.4, 0.3, 1.15, '#26A899')
o.pool(5.35, 8.65, 1.3, 'pool', 'light.office_bathroom_downlight-pool', sort=-40)
o.dot(5.35, 8.65, 4.9, 3.6, 'fixture', 'light.office_bathroom_downlight', sort=205)
# temperature, painted ON the AC wall rather than floating in screen space
# z is bounded: the AC occupies z3.5-4.6 on this wall, so the text lives in the
# clear band below it. Too high and overlay draws it straight over the unit.
o.wall_text(6.55, 1.85, '--', cls='metric wallmetric', eid='office-temp', size=22)
ROOMS.append(o)

# ---------------------------------------------------------------- BEDROOM
b = Room('bedroom', 'BEDROOM', (610, 195), 11, 9, 5.2, '#C2417E', '#B49BD8')
b.plate(4.4, 4.4, 0.02, 5.2, 3.6, '#A98CCF', cls='rug')
# bed
b.box(0.8, 0.8, 0, 5.4, 6.2, 1.05, '#F3F5F8')          # mattress
b.box(0.8, 0.8, 1.05, 5.4, 1.5, 0.5, '#FFFFFF')        # pillows
b.box(0.8, 2.3, 1.05, 5.4, 4.7, 0.35, '#E8628F')       # duvet
b.box(0.55, 0.4, 0, 0.5, 6.9, 2.6, '#8E3160')          # headboard
# nightstands + sockets
b.box(6.6, 0.7, 0, 1.5, 1.5, 1.3, '#F0F2F5')
b.box(6.9, 0.95, 1.3, 0.85, 0.85, 0.5, '#E8628F', eid='switch.tuya_wall_socket_socket_1', cls='plug')
b.box(6.6, 6.4, 0, 1.5, 1.5, 1.3, '#F0F2F5')
b.box(6.9, 6.65, 1.3, 0.85, 0.85, 0.5, '#E8628F', eid='switch.tuya_wall_socket_socket_2', cls='plug')
# LED rings behind headboard (inner/outer)
_rx, _ry = iso(0.10, 3.6, 3.5)
b.add(150, '<g id="light.master_bedroom_led_outer" class="ring"><ellipse cx="%.1f" cy="%.1f" rx="46" ry="26"/></g>' % (_rx, _ry))
b.add(151, '<g id="light.master_bedroom_led_inner" class="ring"><ellipse cx="%.1f" cy="%.1f" rx="28" ry="16"/></g>' % (_rx, _ry))
# 4 ceiling downlights
for i, (lx, ly, ent) in enumerate([
        (2.6, 2.4, 'light.bedroom_downlight_1'), (7.8, 2.4, 'light.wiz_tunable_white_cdad76'),
        (2.6, 6.6, 'light.wiz_tunable_white_cdadae'), (7.8, 6.6, 'light.wiz_tunable_white_9cde0f')]):
    b.pool(lx, ly, 1.9, 'pool', ent + '-pool', sort=-50 + i)
    b.dot(lx, ly, 4.9, 4.0, 'fixture', ent, sort=200 + i)
plant(b, 9.3, 3.6, s=1.0)
ROOMS.append(b)

# ---------------------------------------------------------------- LIVING
l = Room('living', 'LIVING ROOM', (1030, 195), 11, 9, 5.2, '#6FA86A', '#C9B994')
l.plate(3.0, 3.4, 0.02, 6.0, 4.2, '#B8A67E', cls='rug')
# TV on right wall
l.box(2.0, 0.05, 2.2, 5.6, 0.3, 3.0, '#232A34', eid='tv-body')
l.add(3.0, '<polygon class="screen" id="media_player.samsung_7_series_50_ua50nu7470" points="%s"/>' % pts([
    iso(2.2, 0.0, 2.4), iso(7.4, 0.0, 2.4), iso(7.4, 0.0, 5.0), iso(2.2, 0.0, 5.0)]))
# media console + set-top box
l.box(2.0, 0.6, 0, 5.6, 1.4, 1.2, '#B98E5E')
l.box(3.0, 0.9, 1.2, 1.6, 0.9, 0.35, '#39424F', eid='media_player.jio_set_top_box', cls='plug')
# sofa
l.box(1.6, 6.2, 0, 6.2, 2.2, 0.9, '#5E8FBF')
l.box(1.6, 7.6, 0.9, 6.2, 0.8, 1.3, '#6F9ECB')
l.box(1.3, 6.2, 0.9, 0.6, 2.2, 0.85, '#6F9ECB')
l.box(7.5, 6.2, 0.9, 0.6, 2.2, 0.85, '#6F9ECB')
# coffee table
l.box(3.6, 4.4, 0, 2.6, 1.8, 0.75, '#D8C9A6')
# speaker
l.box(9.2, 1.0, 0, 1.0, 1.0, 2.0, '#3A4453', eid='siren.hub', cls='plug')
plant(l, 9.2, 6.6, s=1.15)
ROOMS.append(l)

# ---------------------------------------------------------------- STAIRCASE
s = Room('stairs', 'STAIRCASE', (190, 545), 11, 9, 5.2, '#E08A38', '#E0A92F')
# staircase steps
for i in range(6):
    s.box(1.0 + i * 1.25, 1.0, 0, 1.25, 4.6, 0.55 + i * 0.55, '#F0F3F6', sort=1.0 + i * 1.25 + 1.0)
# step lights (3) on the left wall beside the stairs
for i, (lz, ent) in enumerate([(1.1, 'light.st1'), (2.3, 'light.st2'), (3.5, 'light.st3')]):
    s.box(0.06, 2.2 + i * 1.9, lz, 0.2, 1.1, 0.4, '#FFFFFF', eid=ent, cls='steplight', sort=300 + i)
    px, py = iso(0.3, 2.75 + i * 1.9, lz + 0.2)
    s.add(-40 + i, '<ellipse class="wallpool" id="%s-pool" cx="%.1f" cy="%.1f" rx="34" ry="20"/>' % (ent, px, py))
# borewell pump
s.box(8.4, 6.2, 0, 1.9, 1.9, 1.5, '#5B6674', eid='switch.borewell_motor', cls='pump')
_px, _py = iso(9.35, 7.15, 1.5)
s.add(400, '<g class="pumpring" id="switch.borewell_motor-ring" style="transform-origin:%.1fpx %.1fpx"><circle cx="%.1f" cy="%.1f" r="17"/></g>' % (
    _px, _py, _px, _py))
s.add(401, '<circle class="pumphub" id="switch.borewell_motor-hub" cx="%.1f" cy="%.1f" r="6"/>' % (_px, _py))
ROOMS.append(s)

# ---------------------------------------------------------------- TERRACE
t = Room('terrace', 'TERRACE', (610, 545), 11, 9, 5.2, '#3E9BD6', '#5F6E7E')
t.plate(0.6, 0.6, 0.03, 9.8, 7.8, '#6C7B8C', cls='tiles')
# door on the right wall
t.box(2.4, -0.06, 0, 0.35, 0.5, 4.2, '#2B3946')                     # frame
t.add(500, '<g id="binary_sensor.terrace_door_sensor_door" class="door">'
           '<polygon class="leaf-closed" points="%s"/>'
           '<polygon class="leaf-open" points="%s"/></g>' % (
               pts([iso(2.6, 0.06, 0), iso(5.6, 0.06, 0), iso(5.6, 0.06, 4.0), iso(2.6, 0.06, 4.0)]),
               pts([iso(2.6, 0.06, 0), iso(2.6, 3.0, 0), iso(2.6, 3.0, 4.0), iso(2.6, 0.06, 4.0)])))
# motion sensor high on left wall
t.box(0.06, 6.0, 3.8, 0.3, 0.8, 0.6, '#FFFFFF', eid='binary_sensor.motion_sensor_motion', cls='motion', sort=600)
_mx, _my = iso(0.5, 6.4, 3.6)
t.add(601, '<g id="motion-fx" class="motionfx"><circle class="rip r1" cx="%.1f" cy="%.1f" r="12"/>'
           '<circle class="rip r2" cx="%.1f" cy="%.1f" r="12"/></g>' % (_mx, _my, _mx, _my))
# railing along the front edges
for i in range(7):
    t.box(1.0 + i * 1.45, 8.75, 0, 0.16, 0.16, 1.5, '#8A97A5', sort=200 + i)
t.box(0.9, 8.72, 1.5, 9.4, 0.22, 0.18, '#9FACBA', sort=260)
plant(t, 7.4, 5.4, pot='#C25E3A', s=1.2)
plant(t, 8.9, 2.2, pot='#C25E3A', s=1.0)
ROOMS.append(t)

# ---------------------------------------------------------------- GARDEN
g = Room('garden', 'GARDEN', (1030, 545), 11, 9, 5.2, '#4FB07A', '#4FAE72')
g.plate(0.5, 0.5, 0.03, 10.0, 8.0, '#46A468', cls='lawn')
# hedges along walls
g.box(0.4, 0.4, 0, 10.2, 0.9, 1.1, '#3E9A67')
g.box(0.4, 1.3, 0, 0.9, 7.3, 1.1, '#3E9A67')
# watering valves + spray
for i, (vx, vy, ent) in enumerate([(3.4, 3.2, 'valve.tuya_automated_watering_valve_1'),
                                   (7.0, 5.6, 'valve.tuya_automated_watering_valve_2')]):
    g.box(vx, vy, 0, 0.9, 0.9, 0.8, '#37566B', eid=ent, cls='valve', sort=300 + i)
    px, py = iso(vx + 0.45, vy + 0.45, 0.8)
    g.add(-30 + i, '<ellipse class="spray" id="%s-spray" cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f"/>' % (
        ent, px, py + 8, 2.6 * ELL_RX * U, 2.6 * ELL_RY * U))
    g.add(320 + i, '<g class="jets" id="%s-jets">'
                   '<path d="M%.1f %.1f q14 -16 30 -6"/><path d="M%.1f %.1f q-14 -16 -30 -6"/>'
                   '<path d="M%.1f %.1f q2 -20 4 -22"/></g>' % (ent, px, py, px, py, px, py))
# camera on a pole
g.box(9.6, 1.4, 0, 0.35, 0.35, 3.6, '#4A5A66')
g.box(9.2, 1.1, 3.6, 1.2, 0.9, 0.7, '#DCE3E9', eid='camera.hikvision_ds_2cd1043g0_i_mainstream', cls='cam')
_cx, _cy = iso(9.2, 1.55, 3.95)
g.add(700, '<circle class="camlens" id="camera.hikvision_ds_2cd1043g0_i_mainstream-lens" cx="%.1f" cy="%.1f" r="4.5"/>' % (_cx, _cy))
plant(g, 2.0, 7.0, pot='#B0603A', leaf='#3FA86B', s=1.3)
plant(g, 8.4, 7.6, pot='#B0603A', leaf='#46B575', s=1.1)
ROOMS.append(g)

NAV = {'office': '#office', 'bedroom': '#bedroom', 'living': '#living',
       'stairs': '#stairs', 'terrace': '#garden', 'garden': '#garden'}

# =====================================================================
CSS = """
svg{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",sans-serif}
.room-shadow{fill:rgba(0,0,0,.38);filter:blur(16px)}
.pill rect{fill:rgba(12,16,22,.82);stroke:rgba(255,255,255,.14);transition:fill .25s,stroke .25s}
.pill text{fill:#F2F5F8;font-size:14px;font-weight:700;letter-spacing:2.4px;text-anchor:middle}
/* the pill is the room's tap target -> make that legible */
g[id^="room-"]{cursor:pointer}
g[id^="room-"]:hover rect{fill:rgba(30,40,54,.94);stroke:rgba(255,255,255,.42)}
.metric{fill:#FFFFFF;font-size:26px;font-weight:300;text-anchor:middle;opacity:.92}
/* skewed into the wall plane, so anchor from its start point, not centred */
.wallmetric{text-anchor:start;font-weight:400;opacity:.88;letter-spacing:1px}
.rug,.tiles,.lawn{opacity:.9}
.contact{fill:#000;filter:blur(5px);pointer-events:none}

/* ---------- standing bar lamp (a switch, so on/off only -- no dimming) ---------- */
.bar polygon{transition:fill .45s,filter .45s}
.bar.bar-on .f-t,.bar.bar-on .f-r,.bar.bar-on .f-l{
  fill:#FFE9BC;filter:drop-shadow(0 0 11px rgba(255,201,120,.95))}

/* ---------- badges ---------- */
.badge{cursor:pointer}
.badge-ring{fill:none;stroke:rgba(255,255,255,.55);stroke-width:1.5}
.badge-core{fill:#2F6BFF}
.badge-hub{fill:#fff}
.badge:hover .badge-core{fill:#4B82FF}
.badge:hover .badge-ring{stroke:#fff}

/* ---------- lights ---------- */
.pool{opacity:0;transition:opacity .55s ease;pointer-events:none}
.poolel{fill:url(#poolg)}
.beam{fill:url(#beamg)}
.wallpool{fill:url(#poolg);opacity:0;filter:blur(5px);transition:opacity .55s ease}
/* Off-state fixtures must still be findable -- they are the tap targets.
   A visible ring plus a brighter core beats a faint dot. */
.fixture{fill:rgba(255,255,255,.55);stroke:rgba(255,255,255,.34);stroke-width:1.4;
  transition:fill .4s,filter .4s,stroke .4s}
.light-on .pool,.pool.light-on{opacity:1}
.light-on .wallpool,.wallpool.light-on{opacity:1}
.light-on.fixture,.fixture.light-on{fill:#FFF6DF;stroke:rgba(255,226,160,.95);
  filter:drop-shadow(0 0 16px rgba(255,206,120,1))}
g[id^="light."]{cursor:pointer}

/* LED strip */
.strip polygon{transition:fill .5s}
.strip.light-on .f-t{fill:#FFE6B0;filter:drop-shadow(0 0 10px rgba(255,190,90,.9))}
.strip.light-on .f-r{fill:#FFCE7A}
.strip.light-on .f-l{fill:#F2B45E}

/* bedside LED rings */
.ring ellipse{fill:none;stroke:rgba(255,255,255,.18);stroke-width:4;transition:stroke .5s}
.ring.light-on ellipse{stroke:#FF7BC0;filter:drop-shadow(0 0 12px rgba(255,90,170,.9))}

/* step lights */
.steplight .f-t,.steplight .f-r,.steplight .f-l{transition:fill .4s}
.steplight.light-on .f-t{fill:#FFF0CE;filter:drop-shadow(0 0 8px rgba(255,214,140,.95))}

/* ---------- AC ---------- */
.fan-ring{fill:none;stroke:rgba(120,140,160,.5);stroke-width:1.5}
.fan-b{fill:rgba(140,160,180,.6);transition:fill .5s}
.ac.ac-on .f-r,.ac.ac-on .f-t{fill:#DDF3FB}
.fan.ac-running .fan-b,.ac-running .fan-b{fill:#6FC3DD}
.fan.ac-running .fan-ring,.ac-running .fan-ring{stroke:#6FC3DD}
.fan.ac-running,.ac-running .fan{animation:spin 1.3s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}

/* ---------- plugs / screens ---------- */
.bolt{fill:rgba(255,255,255,.30);transition:fill .4s,filter .4s}
.plug-on .bolt,.bolt.plug-on{fill:#5CB884;filter:drop-shadow(0 0 8px rgba(92,184,132,.95))}
.plug.plug-on .f-t{filter:drop-shadow(0 0 6px rgba(92,184,132,.5))}
.screen{fill:#171C24;transition:fill .5s}
.screen.on{fill:#4FA8E0;filter:drop-shadow(0 0 16px rgba(79,168,224,.8))}

/* ---------- pump ---------- */
.pumpring{fill:none}
.pumpring circle{fill:none;stroke:rgba(255,255,255,.18);stroke-width:2.5;transition:stroke .4s}
.pumphub{fill:rgba(255,255,255,.35);transition:fill .4s}
.pumpring.pump-on circle,.pump-on .pumpring circle{stroke:#E8A33D}
.pumpring.pump-on,.pump-on .pumpring{animation:pulse 1.5s ease-in-out infinite}
.pumphub.pump-on,.pump-on .pumphub{fill:#E8A33D;filter:drop-shadow(0 0 9px rgba(232,163,61,.95))}
@keyframes pulse{0%,100%{transform:scale(1);opacity:1}50%{transform:scale(1.5);opacity:.25}}

/* ---------- door ---------- */
.leaf-closed{fill:#9FB0C0;stroke:rgba(0,0,0,.2);stroke-width:1;transition:opacity .55s}
.leaf-open{fill:#AEBECC;stroke:#E5484D;stroke-width:2;opacity:0;transition:opacity .55s}
.door.door-open .leaf-closed{opacity:0}
.door.door-open .leaf-open{opacity:1;filter:drop-shadow(0 0 9px rgba(229,72,77,.85))}

/* ---------- motion ---------- */
.rip{fill:none;stroke:#E8A33D;stroke-width:2.5;opacity:0;transform-box:fill-box;transform-origin:center}
.motion .f-t{transition:fill .4s}
.motion-on .f-t{fill:#FFD98A}
.motionfx.motion-on .rip{animation:rip 1.9s ease-out infinite}
.motionfx.motion-on .rip.r2{animation-delay:.65s}
@keyframes rip{0%{opacity:.9;transform:scale(.25)}100%{opacity:0;transform:scale(2.6)}}

/* ---------- garden ---------- */
.spray{fill:#6FC3DD;opacity:0;transition:opacity .5s}
.spray.valve-open{opacity:.7}
.jets path{fill:none;stroke:#A8E4F5;stroke-width:3.2;stroke-linecap:round;opacity:0}
.jets.valve-open path{opacity:.9;animation:jet 1.1s ease-out infinite}
.jets.valve-open path:nth-child(2){animation-delay:.25s}
.jets.valve-open path:nth-child(3){animation-delay:.5s}
@keyframes jet{0%{opacity:0;transform:translateY(4px) scale(.6)}35%{opacity:.95}100%{opacity:0;transform:translateY(-6px) scale(1.15)}}
.camlens{fill:#2B3946;transition:fill .4s}
.cam-on .camlens,.camlens.cam-on{fill:#E5484D;filter:drop-shadow(0 0 7px rgba(229,72,77,.9))}

@media (prefers-reduced-motion:reduce){
  .ac-running .fan,.pump-on .pumpring,.motionfx.motion-on .rip,.jets.valve-open path{animation:none}
}
"""

# =====================================================================
import xml.etree.ElementTree as ET

DEFS = ('<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#101826"/>'
        '<stop offset="55%" stop-color="#0C1119"/>'
        '<stop offset="100%" stop-color="#080B10"/></linearGradient>'
        '<radialGradient id="poolg"><stop offset="0%" stop-color="#FFF8E6" stop-opacity="1"/>''<stop offset="50%" stop-color="#FFD277" stop-opacity=".82"/>''<stop offset="100%" stop-color="#FFBE45" stop-opacity="0"/></radialGradient>'
        '<linearGradient id="beamg" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#FFEEC2" stop-opacity=".42"/>'
        '<stop offset="55%" stop-color="#FFD98F" stop-opacity=".20"/>'
        '<stop offset="100%" stop-color="#FFC85C" stop-opacity="0"/></linearGradient>'
        '<radialGradient id="amb" cx="50%" cy="0%" r="80%">'
        '<stop offset="0%" stop-color="#2B7FB8" stop-opacity=".28"/>'
        '<stop offset="100%" stop-color="#2B7FB8" stop-opacity="0"/></radialGradient></defs>')


def emit(svg, path, label):
    """Minify, validate, write, and report."""
    svg = re.sub(r'>\s+<', '><', svg)
    svg = re.sub(r'\n\s*', ' ', svg)
    svg = re.sub(r'  +', ' ', svg)
    ET.fromstring(svg)                       # fails loudly on malformed output
    open(path, 'w').write(svg)
    ids = re.findall(r'id="([^"]+)"', svg)
    print('%-16s %6d bytes   md5 %s   entity-ids %2d' % (
        label, len(svg.encode()), hashlib.md5(svg.encode()).hexdigest(),
        len([i for i in ids if '.' in i])))
    return svg


# ---------------------------------------------------------------- overview
W_CANVAS, H_CANVAS = 1260, 750
parts = ['<svg xmlns="http://www.w3.org/2000/svg" id="fp-root" '
         'viewBox="0 0 %d %d" width="%d" height="%d">'
         % (W_CANVAS, H_CANVAS, W_CANVAS, H_CANVAS)]
parts.append('<style>%s</style>' % CSS)
parts.append(DEFS)
parts.append('<rect width="%d" height="%d" fill="url(#bg)"/>' % (W_CANVAS, H_CANVAS))
parts.append('<rect width="%d" height="%d" fill="url(#amb)"/>' % (W_CANVAS, H_CANVAS))
parts.append('<text x="56" y="58" fill="#F2F5F8" font-size="27" font-weight="800" '
             'letter-spacing="7">MY HOME</text>')
parts.append('<text x="%d" y="58" fill="#5A6473" font-size="14" letter-spacing="3" '
             'text-anchor="end">sarthak.local</text>' % (W_CANVAS - 56))

for rm in ROOMS:
    parts.append(rm.render())
for rm in ROOMS:
    parts.append(rm.label())
parts.append('</svg>')

svg = emit("".join(parts), 'iso.svg', 'overview')
b64 = base64.b64encode(svg.encode()).decode()
open('iso.b64', 'w').write(b64)


# ---------------------------------------------------------------- room views
# The room screen is the same geometry as the overview, framed tightly by the
# viewBox instead of being redrawn at a larger unit scale. Identical output,
# far bigger on screen -- and the entity ids carry over untouched.
ROOM_CSS = """
/* drawer: the SVG's own height drives the card's height, which displaces the
   controls card below it. Percentages will not work here -- the parent is
   auto-height, so a percentage resolves to auto. Viewport units do. */
/* !important is required: ha-floorplan injects its own `svg{...}` rules into
   the same shadow root and they otherwise win. */
#fp-root{height:78vh!important;transition:height .34s cubic-bezier(.4,0,.2,1)}
#fp-root.drawer-open{height:44vh!important}
@media (max-width:700px){
  #fp-root{height:58vh!important}
  #fp-root.drawer-open{height:34vh!important}
}
.rtitle{fill:#F2F5F8;font-size:26px;font-weight:800;letter-spacing:6px;text-anchor:middle}
.handle{cursor:pointer}
.handle rect{fill:rgba(18,24,33,.9);stroke:rgba(255,255,255,.18);transition:fill .25s,stroke .25s}
.handle text{fill:#C9D2DD;font-size:13px;font-weight:700;letter-spacing:2.2px;text-anchor:middle}
.handle:hover rect{fill:rgba(32,42,56,.96);stroke:rgba(255,255,255,.45)}
.handle .chev{fill:none;stroke:#C9D2DD;stroke-width:2.2;stroke-linecap:round;transition:transform .34s}
#fp-root.drawer-open .handle .chev{transform:rotate(180deg)}
"""


def room_bbox(rm, pad=20, bottom_extra=50):
    """Tight frame around one room, in the room's own local iso coordinates.

    Keep the vertical padding mean. An isometric room is taller than it is
    wide once walls are included, so on any landscape screen the frame is
    height-limited: every unit of vertical padding scales the whole room down,
    while horizontal padding costs nothing. Hence a small `pad` and a
    `bottom_extra` sized to the handle and nothing more.
    """
    W, D, H = rm.W, rm.D, rm.H
    t, fd = 0.45, 0.55
    cs = []
    for zz in (0.0, H * 1.06):
        for xx in (-t, W + t):
            for yy in (-t, D + t):
                cs.append(iso(xx, yy, zz))
    for xx, yy in ((0.0, D), (W, D), (W, 0.0)):
        cs.append(iso(xx, yy, -fd))
    xs = [c[0] for c in cs]
    ys = [c[1] for c in cs]
    minx, maxx = min(xs) - pad, max(xs) + pad
    miny, maxy = min(ys) - pad - 30, max(ys) + pad + bottom_extra
    return minx, miny, maxx - minx, maxy - miny


def build_room(rm):
    """One room, alone, framed to fill the screen."""
    saved = rm.pos
    rm.pos = (0.0, 0.0)                      # render in local coordinates
    try:
        vx, vy, vw, vh = room_bbox(rm)
        p = ['<svg xmlns="http://www.w3.org/2000/svg" id="fp-root" '
             'viewBox="%.1f %.1f %.1f %.1f" preserveAspectRatio="xMidYMid meet">'
             % (vx, vy, vw, vh)]
        p.append('<style>%s%s</style>' % (CSS, ROOM_CSS))
        p.append(DEFS)
        for grad in ('bg', 'amb'):
            p.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="url(#%s)"/>'
                     % (vx, vy, vw, vh, grad))
        p.append('<text class="rtitle" x="%.1f" y="%.1f">%s</text>'
                 % (vx + vw / 2.0, vy + 30, rm.name))
        p.append(rm.render())
        # drawer handle -- the room's own affordance for the controls tray
        hx, hy = vx + vw / 2.0, vy + vh - 28
        p.append('<g id="drawer-handle" class="handle">'
                 '<rect x="%.1f" y="%.1f" width="168" height="36" rx="18"/>'
                 '<text x="%.1f" y="%.1f">CONTROLS</text>'
                 '<path class="chev" d="M%.1f %.1f l5 5 l5 -5"/>'
                 '</g>'
                 % (hx - 84, hy - 18, hx - 8, hy + 5,
                    hx + 52, hy - 2))
        p.append('</svg>')
        return "".join(p)
    finally:
        rm.pos = saved


emit(build_room(o), 'room-office.svg', 'room-office')
