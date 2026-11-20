"""Optional PNG schematic renderer for LogicCircuit circuits (requires Pillow)."""

from __future__ import annotations

from pathlib import Path
from typing import Union

from .gates import parse_gate_guid
from .project import Circuit


def render_circuit_png(
    circuit: Circuit,
    output_path: Union[str, Path],
    scale: int = 12,
    padding: int = 6,
) -> Path:
    """Render a :class:`Circuit` schematic to a PNG image using Pillow."""
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise ImportError(
            "Pillow is required for PNG rendering. Install with: pip install 'pylogiccircuit[preview]'"
        ) from exc

    pin_by_id = {p.pin_id: p for p in circuit.pins}
    lc_by_id = {c.circuit_id: c for c in circuit.project.circuits}

    max_x = max(
        [s.x + 10 for s in circuit.symbols]
        + [max(w.x1, w.x2) for w in circuit.wires]
        + [10]
    ) + padding
    max_y = max(
        [s.y + 10 for s in circuit.symbols]
        + [max(w.y1, w.y2) for w in circuit.wires]
        + [10]
    ) + padding

    img = Image.new("RGB", (max_x * scale, max_y * scale), "white")
    draw = ImageDraw.Draw(img)

    # Subtle background grid
    for gx in range(0, max_x * scale, scale * 5):
        draw.line([(gx, 0), (gx, max_y * scale)], fill=(242, 242, 242))
    for gy in range(0, max_y * scale, scale * 5):
        draw.line([(0, gy), (max_x * scale, gy)], fill=(242, 242, 242))

    # Wires
    for w in circuit.wires:
        draw.line(
            [(w.x1 * scale, w.y1 * scale), (w.x2 * scale, w.y2 * scale)],
            fill=(30, 100, 200),
            width=max(2, scale // 6),
        )

    # Symbols
    for s in circuit.symbols:
        x, y = s.x, s.y
        if s.circuit_id in pin_by_id:
            pdef = pin_by_id[s.circuit_id]
            w, h = 2, 2
            color = (255, 240, 200)
            label = pdef.name
        elif s.circuit_id in lc_by_id:
            sub = lc_by_id[s.circuit_id]
            w, h, _ = sub.symbol_layout()
            color = (210, 250, 220) if h <= 5 else (255, 220, 240)
            label = sub.notation or sub.name
        else:
            gspec = parse_gate_guid(s.circuit_id)
            if gspec is not None:
                w, h = gspec.width, gspec.height
                color = (230, 240, 255)
                label = gspec.kind
            else:
                w, h = 3, 4
                color = (235, 235, 235)
                label = s.label or s.circuit_id[-6:]

        draw.rectangle(
            [x * scale, y * scale, (x + w) * scale, (y + h) * scale],
            fill=color,
            outline=(40, 40, 40),
            width=2,
        )
        draw.text((x * scale + 3, y * scale + 2), label[:10], fill=(0, 0, 0))

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out
