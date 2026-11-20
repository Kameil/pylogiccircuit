"""Optional PNG schematic renderer for LogicCircuit circuits (requires Pillow)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from .gates import parse_gate_guid
from .project import Circuit

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)

_MONO_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
)


def _load_font(size: int, mono: bool = False):
    from PIL import ImageFont

    candidates = _MONO_CANDIDATES if mono else _FONT_CANDIDATES
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _find_junction_points(wires) -> List[Tuple[int, int]]:
    """Find grid points where 3+ wire ends meet or an endpoint touches another segment's interior."""
    endpoint_count: Counter[Tuple[int, int]] = Counter()
    segs: List[Tuple[int, int, int, int]] = []
    for w in wires:
        p1, p2 = (w.x1, w.y1), (w.x2, w.y2)
        endpoint_count[p1] += 1
        endpoint_count[p2] += 1
        segs.append((w.x1, w.y1, w.x2, w.y2))

    junctions = {pt for pt, cnt in endpoint_count.items() if cnt >= 3}

    for pt in endpoint_count:
        px, py = pt
        for x1, y1, x2, y2 in segs:
            if pt == (x1, y1) or pt == (x2, y2):
                continue
            if x1 == x2 == px and min(y1, y2) < py < max(y1, y2):
                junctions.add(pt)
                break
            if y1 == y2 == py and min(x1, x2) < px < max(x1, x2):
                junctions.add(pt)
                break
    return sorted(junctions)


def render_circuit_png(
    circuit: Circuit,
    output_path: Union[str, Path],
    scale: int = 16,
    padding: int = 3,
    *,
    title: Optional[str] = None,
    show_header: bool = True,
    show_legend: bool = True,
) -> Path:
    """Render a crisp :class:`Circuit` schematic preview to a PNG image using Pillow.

    Args:
        circuit: Circuit to render.
        output_path: Destination PNG file path.
        scale: Pixels per LogicCircuit grid unit (default: 16).
        padding: Extra grid units around the schematic bounds (default: 3).
        title: Optional custom header title (defaults to ``"{name} ({notation})"``).
        show_header: Whether to draw a top title/stats bar.
        show_legend: Whether to draw a bottom color legend.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise ImportError(
            "Pillow is required for PNG rendering. Install with: pip install 'pylogiccircuit[preview]'"
        ) from exc

    pin_by_id = {p.pin_id: p for p in circuit.pins}
    lc_by_id = {c.circuit_id: c for c in circuit.project.circuits}

    # Compute exact bounding box of symbols + wires
    xs: List[int] = []
    ys: List[int] = []
    symbol_boxes: List[Tuple[object, int, int, int, int, str, str, bool, List[Tuple[int, int]]]] = []

    for s in circuit.symbols:
        x, y = s.x, s.y
        if s.circuit_id in pin_by_id:
            pdef = pin_by_id[s.circuit_id]
            w, h = 2, 2
            kind = "input" if pdef.pin_type == "Input" else "output"
            label = pdef.name
            inv = pdef.inverted
            jams = [pdef.jam]
        elif s.circuit_id in lc_by_id:
            sub = lc_by_id[s.circuit_id]
            w, h, offs = sub.symbol_layout()
            kind = "sub"
            label = sub.notation or sub.name
            inv = False
            jams = [(x + dx, y + dy) for dx, dy in offs.values()]
        else:
            gspec = parse_gate_guid(s.circuit_id)
            if gspec is not None:
                w, h = gspec.width, gspec.height
                kind = "clock" if gspec.kind == "CLOCK" else ("led" if gspec.kind == "LED" else "gate")
                label = gspec.kind if gspec.n_inputs <= 2 else f"{gspec.kind}{gspec.n_inputs}"
                inv = gspec.inverted
                jams = [(x + dx, y + dy) for dx, dy in gspec.input_offsets()]
                out_off = gspec.output_offset()
                if out_off is not None:
                    jams.append((x + out_off[0], y + out_off[1]))
            else:
                w, h = 3, 4
                kind = "other"
                label = s.label or s.circuit_id[-6:]
                inv = False
                jams = []

        symbol_boxes.append((s, x, y, w, h, kind, label, inv, jams))
        xs.extend([x, x + w])
        ys.extend([y, y + h])

    for wire in circuit.wires:
        xs.extend([wire.x1, wire.x2])
        ys.extend([wire.y1, wire.y2])

    min_x = max(0, (min(xs) if xs else 0) - padding)
    min_y = max(0, (min(ys) if ys else 0) - padding)
    max_x = (max(xs) if xs else 10) + padding
    max_y = (max(ys) if ys else 10) + padding

    header_h = max(38, int(scale * 2.6)) if show_header else 0
    legend_h = max(32, int(scale * 2.1)) if show_legend else 0
    canvas_w = max(420, (max_x - min_x) * scale)
    canvas_h = (max_y - min_y) * scale + header_h + legend_h

    def to_px(gx: float, gy: float) -> Tuple[float, float]:
        return ((gx - min_x) * scale, (gy - min_y) * scale + header_h)

    img = Image.new("RGB", (canvas_w, canvas_h), "#FFFFFF")
    draw = ImageDraw.Draw(img)

    font_title = _load_font(max(13, int(scale * 0.95)))
    font_sub = _load_font(max(10, int(scale * 0.68)), mono=True)
    font_lbl = _load_font(max(9, int(scale * 0.66)))
    font_pin = _load_font(max(8, int(scale * 0.58)))

    # 1. Subtle grid inside schematic area
    grid_bottom = canvas_h - legend_h
    for gx in range(min_x, max_x + 1):
        px, _ = to_px(gx, min_y)
        col = "#E5E7EB" if gx % 5 == 0 else "#F3F4F6"
        draw.line([(px, header_h), (px, grid_bottom)], fill=col, width=1)
    for gy in range(min_y, max_y + 1):
        _, py = to_px(min_x, gy)
        col = "#E5E7EB" if gy % 5 == 0 else "#F3F4F6"
        draw.line([(0, py), (canvas_w, py)], fill=col, width=1)

    # 2. Wires + T-junction dots
    wire_w = max(2, scale // 7)
    wire_color = "#1D4ED8"
    for wire in circuit.wires:
        p1 = to_px(wire.x1, wire.y1)
        p2 = to_px(wire.x2, wire.y2)
        draw.line([p1, p2], fill=wire_color, width=wire_w)

    j_rad = max(2.5, scale * 0.22)
    for jx, jy in _find_junction_points(circuit.wires):
        cx, cy = to_px(jx, jy)
        draw.ellipse([cx - j_rad, cy - j_rad, cx + j_rad, cy + j_rad], fill=wire_color)

    # 3. Symbols
    palette: Dict[str, Tuple[str, str, str]] = {
        "input":  ("#FEF3C7", "#B45309", "#78350F"),
        "output": ("#D1FAE5", "#047857", "#064E3B"),
        "gate":   ("#DBEAFE", "#1E40AF", "#1E3A8A"),
        "sub":    ("#EDE9FE", "#6D28D9", "#4C1D95"),
        "clock":  ("#FCE7F3", "#BE185D", "#831843"),
        "led":    ("#FEE2E2", "#B91C1C", "#7F1D1D"),
        "other":  ("#F3F4F6", "#4B5563", "#1F2937"),
    }

    pin_rad = max(2.0, scale * 0.16)
    for _, x, y, w, h, kind, label, inv, jams in symbol_boxes:
        fill, outline, text_col = palette[kind]
        x0, y0 = to_px(x, y)
        x1, y1 = to_px(x + w, y + h)
        radius = max(3, scale // 4)
        draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill, outline=outline, width=2)

        # Pin jam markers
        for jx, jy in jams:
            px, py = to_px(jx, jy)
            draw.ellipse([px - pin_rad, py - pin_rad, px + pin_rad, py + pin_rad], fill=outline)

        # Inversion bubble on inverted gates/pins
        if inv and kind == "gate":
            bx, by = to_px(x + w, y + h / 2.0)
            br = max(3.0, scale * 0.24)
            draw.ellipse([bx - br, by - br, bx + br, by + br], fill="#FFFFFF", outline=outline, width=2)

        # Centered label inside box (auto-shrink font if wider than box)
        base_size = max(8, int(scale * (0.58 if kind in ("input", "output") else 0.66)))
        short_lbl = label if len(label) <= 10 else label[:9] + "…"
        box_w = (x1 - x0) - 6
        fnt = _load_font(base_size)
        bbox = draw.textbbox((0, 0), short_lbl, font=fnt)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        cur_size = base_size
        while tw > box_w and cur_size > 7:
            cur_size -= 1
            fnt = _load_font(cur_size)
            bbox = draw.textbbox((0, 0), short_lbl, font=fnt)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx = (x0 + x1 - tw) / 2.0
        ty = (y0 + y1 - th) / 2.0 - bbox[1]
        draw.text((tx, ty), short_lbl, fill=text_col, font=fnt)

    # 4. Header bar
    if show_header:
        draw.rectangle([0, 0, canvas_w, header_h], fill="#0F172A")
        hdr_title = title or (
            f"{circuit.name} ({circuit.notation})" if circuit.notation and circuit.notation != circuit.name else circuit.name
        )
        n_in = sum(1 for p in circuit.pins if p.pin_type == "Input")
        n_out = sum(1 for p in circuit.pins if p.pin_type == "Output")
        stats = f"in:{n_in}  out:{n_out}  syms:{len(circuit.symbols)}  wires:{len(circuit.wires)}"
        tb = draw.textbbox((0, 0), hdr_title, font=font_title)
        tw_hdr, th_hdr = tb[2] - tb[0], tb[3] - tb[1]
        sb = draw.textbbox((0, 0), stats, font=font_sub)
        sw, sh = sb[2] - sb[0], sb[3] - sb[1]
        # Shrink title slightly if needed so title and stats never collide
        cur_t_size = max(13, int(scale * 0.95))
        t_font = font_title
        while 12 + tw_hdr + 20 + sw + 12 > canvas_w and cur_t_size > 11:
            cur_t_size -= 1
            t_font = _load_font(cur_t_size)
            tb = draw.textbbox((0, 0), hdr_title, font=t_font)
            tw_hdr, th_hdr = tb[2] - tb[0], tb[3] - tb[1]
        draw.text((12, (header_h - th_hdr) / 2.0 - tb[1]), hdr_title, fill="#F8FAFC", font=t_font)
        if 12 + tw_hdr + 16 + sw + 12 <= canvas_w:
            draw.text((canvas_w - sw - 12, (header_h - sh) / 2.0 - sb[1]), stats, fill="#94A3B8", font=font_sub)

    # 5. Footer legend
    if show_legend:
        ly0 = canvas_h - legend_h
        draw.rectangle([0, ly0, canvas_w, canvas_h], fill="#F8FAFC")
        draw.line([(0, ly0), (canvas_w, ly0)], fill="#CBD5E1", width=1)
        items = [
            ("Input", "input"),
            ("Output", "output"),
            ("Gate", "gate"),
            ("Subcircuit", "sub"),
        ]
        cx = 12
        cy = ly0 + (legend_h - 12) // 2
        for text, key in items:
            fill, outline, _ = palette[key]
            draw.rounded_rectangle([cx, cy, cx + 12, cy + 12], radius=2, fill=fill, outline=outline, width=2)
            draw.text((cx + 16, cy - 1), text, fill="#334155", font=font_pin)
            tb = draw.textbbox((0, 0), text, font=font_pin)
            cx += 16 + (tb[2] - tb[0]) + 18
        # Wire / Junction swatch
        draw.line([(cx, cy + 6), (cx + 14, cy + 6)], fill=wire_color, width=2)
        draw.ellipse([cx + 5, cy + 3, cx + 10, cy + 8], fill=wire_color)
        draw.text((cx + 18, cy - 1), "Wire / Junction", fill="#334155", font=font_pin)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, format="PNG")
    return out
