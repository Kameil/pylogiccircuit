# Live Preview in Zed

`pylogiccircuit watch` gives you an instant side-by-side live schematic preview directly inside **[Zed](https://zed.dev/)** as you edit `.py` circuit scripts or `.CircuitProject` files.

Because Zed automatically reloads open `.png` images and Markdown previews whenever files change on disk, `pylogiccircuit watch` writes updated previews **atomically** on every save (`Ctrl+S` / `Cmd+S`) — with zero flicker and zero extra dependencies beyond `Pillow`.

---

## Quick Setup in Zed (3 Steps)

This repository already ships with ready-to-use Zed tasks in [`.zed/tasks.json`](../.zed/tasks.json).

1. **Open any circuit file** in Zed (for example, [`examples/half_adder.py`](../examples/half_adder.py) or [`examples/alu_4bit_74ls382.py`](../examples/alu_4bit_74ls382.py)).
2. **Spawn the live preview task**: press `Alt+Shift+T` (or open the Command Palette `Ctrl+Shift+P` → `task: spawn`) and pick one of:
   - **`pylogiccircuit: Live Preview (PNG in Zed split)`** — updates `.pylogiccircuit_preview.png` on every save.
   - **`pylogiccircuit: Live Preview (PNG + Markdown Truth Table)`** — updates both `.pylogiccircuit_preview.png` and `.pylogiccircuit_preview.md` (schematic + verification status + live truth table).
   - **`pylogiccircuit: Live Preview (Browser http://127.0.0.1:8765)`** — also starts a lightweight local auto-reloading web viewer.
3. **Open the preview in a right split pane**:
   - **PNG mode**: open `.pylogiccircuit_preview.png` in a split beside your code. Every time you save, Zed refreshes the image automatically.
   - **Markdown mode**: open `.pylogiccircuit_preview.md` and run `markdown: open preview to the side` (`Ctrl+K V` / Command Palette) to see the schematic, short-circuit check, and truth table together.

---

## Global Zed Tasks (Optional — Use in Any Folder)

If you have `pylogiccircuit` installed globally (`pip install "pylogiccircuit[preview] @ git+https://github.com/Kameil/pylogiccircuit.git"`), you can add this task to your global `~/.config/zed/tasks.json` so it works in **any** project:

```json
[
  {
    "label": "pylogiccircuit: Live Preview (PNG)",
    "command": "pylogiccircuit",
    "args": [
      "watch",
      "$ZED_FILE",
      "-o",
      ".pylogiccircuit_preview.png"
    ],
    "use_new_terminal": false,
    "allow_concurrent_runs": false,
    "reveal": "always"
  },
  {
    "label": "pylogiccircuit: Live Preview (PNG + Markdown)",
    "command": "pylogiccircuit",
    "args": [
      "watch",
      "$ZED_FILE",
      "-o",
      ".pylogiccircuit_preview.png",
      "--md",
      ".pylogiccircuit_preview.md"
    ],
    "use_new_terminal": false,
    "allow_concurrent_runs": false,
    "reveal": "always"
  }
]
```

---

## How `.py` Script Discovery Works

When watching a Python file, `pylogiccircuit watch` automatically finds your circuit in any of these styles:

1. **Top-level variable**: a `Project` or `Circuit` variable defined directly in the script (e.g., `proj = Project(...)`).
2. **Builder function**: a zero-argument function returning a `Project` or `Circuit` (e.g., `def build_half_adder() -> Project:`).
3. **`if __name__ == "__main__":` script**: falls back to running the script and capturing the constructed `Project`.
4. **`.CircuitProject` XML file**: reloads the XML directly on every save.

### Error Resilience
If you save while mid-edit (e.g., a `SyntaxError` or `RoutingError`), `pylogiccircuit watch` **does not crash** — it renders a red diagnostic error card directly into `.pylogiccircuit_preview.png` (and `.pylogiccircuit_preview.md`), then seamlessly restores the schematic as soon as you fix the error and save again.

---

## CLI Options Reference

```bash
pylogiccircuit watch <source.py | project.CircuitProject> [options]
```

| Flag | Default | Description |
| --- | --- | --- |
| `-o, --output PATH` | `.pylogiccircuit_preview.png` | Destination PNG file updated atomically on save |
| `--md, --markdown PATH` | *(disabled)* | Also write a live Markdown report (image + verification + truth table) |
| `-c, --circuit NAME` | *(main circuit)* | Specific circuit name or GUID to render |
| `--scale N` | `16` | Pixels per LogicCircuit grid unit |
| `--interval SEC` | `0.25` | File polling interval in seconds |
| `--serve [PORT]` | *(disabled)* | Start a local auto-refreshing web viewer (default port `8765`) |
| `--once` | `false` | Render once and exit |
