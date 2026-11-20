"""Live-reload preview watcher for LogicCircuit (.py and .CircuitProject) files.

Designed for seamless side-by-side live previews in editors like Zed (which auto-reload
open PNG images and Markdown previews on file change) as well as an optional built-in
local web viewer (``--serve``) with zero extra dependencies.
"""

from __future__ import annotations

import inspect
import json
import os
import runpy
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .preview import _load_font, render_circuit_png
from .project import Circuit, Project
from .simulator import Simulator


@dataclass
class RenderSnapshot:
    """Outcome of a single build/render pass during watch mode."""

    ok: bool
    timestamp: str
    source_path: Path
    png_path: Path
    md_path: Optional[Path] = None
    circuit_name: Optional[str] = None
    error: Optional[str] = None
    verify_errors: Tuple[str, ...] = ()
    n_inputs: int = 0
    n_outputs: int = 0
    n_symbols: int = 0
    n_wires: int = 0
    truth_table_md: Optional[str] = None
    oscillated: bool = False


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _atomic_write_text(path: Path, text: str) -> None:
    _atomic_write_bytes(path, text.encode("utf-8"))


def _render_error_png(
    output_path: Path,
    source_name: str,
    error_text: str,
) -> None:
    """Render a clean diagnostic error card PNG so editor previews stay informative."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return

    width, height = 760, 320
    img = Image.new("RGB", (width, height), "#FEF2F2")
    draw = ImageDraw.Draw(img)

    font_hdr = _load_font(16)
    font_sub = _load_font(12, mono=True)

    draw.rectangle([0, 0, width, 44], fill="#991B1B")
    draw.text((14, 12), f"pylogiccircuit watch — Error in {source_name}", fill="#FFFFFF", font=font_hdr)

    lines: List[str] = []
    for raw in error_text.strip().splitlines():
        while len(raw) > 84:
            lines.append(raw[:84])
            raw = raw[84:]
        lines.append(raw)
    lines = lines[-12:]  # show most relevant tail lines

    y = 60
    for line in lines:
        draw.text((14, y), line, fill="#7F1D1D", font=font_sub)
        y += 20

    tmp = output_path.with_name(f".{output_path.stem}.tmp.{os.getpid()}.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(tmp, format="PNG")
    os.replace(tmp, output_path)


def _extract_project_from_namespace(ns: Dict[str, Any], source_file: str) -> Optional[Project]:
    """Locate a Project (or Circuit) in a Python module namespace."""
    projects = [v for v in ns.values() if isinstance(v, Project)]
    if projects:
        return projects[-1]

    circuits = [v for v in ns.values() if isinstance(v, Circuit)]
    if circuits:
        return circuits[-1].project

    # Look for zero-arg builder functions defined in this script
    preferred: List[Callable[[], Any]] = []
    fallback: List[Callable[[], Any]] = []
    resolved_src = str(Path(source_file).resolve())

    for name, obj in ns.items():
        if name.startswith("_") or not callable(obj) or inspect.isclass(obj):
            continue
        code = getattr(obj, "__code__", None)
        if code is None:
            continue
        try:
            fn_file = str(Path(code.co_filename).resolve())
        except OSError:
            continue
        if fn_file != resolved_src:
            continue
        try:
            sig = inspect.signature(obj)
        except (TypeError, ValueError):
            continue
        required = [
            p
            for p in sig.parameters.values()
            if p.default is inspect.Parameter.empty
            and p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        ]
        if required:
            continue
        lower = name.lower()
        if lower.startswith(("build", "create", "make")) or lower in ("project", "circuit", "main"):
            preferred.append(obj)
        else:
            fallback.append(obj)

    for fn in preferred + fallback:
        res = fn()
        if isinstance(res, Project):
            return res
        if isinstance(res, Circuit):
            return res.project

    return None


def load_project_from_source(source_path: Union[str, Path]) -> Project:
    """Load a :class:`Project` from either a ``.CircuitProject`` XML file or a ``.py`` script."""
    src = Path(source_path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Source file not found: {src}")

    if src.suffix.lower() == ".circuitproject":
        return Project.load(src)

    if src.suffix.lower() != ".py":
        raise ValueError(
            f"Unsupported file type {src.suffix!r}. Expected '.py' or '.CircuitProject'."
        )

    src_dir = str(src.parent)
    added_sys_path = False
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
        added_sys_path = True

    try:
        ns = runpy.run_path(str(src), run_name="__pylogiccircuit_watch__")
        proj = _extract_project_from_namespace(ns, str(src))
        if proj is not None:
            return proj

        # Fallback: run with __name__ == '__main__' while tracking instantiated Projects
        captured: List[Project] = []
        orig_init = Project.__init__

        def _tracking_init(self: Project, *args: Any, **kwargs: Any) -> None:
            orig_init(self, *args, **kwargs)
            captured.append(self)

        Project.__init__ = _tracking_init  # type: ignore[method-assign]
        try:
            ns_main = runpy.run_path(str(src), run_name="__main__")
        finally:
            Project.__init__ = orig_init  # type: ignore[method-assign]

        proj = _extract_project_from_namespace(ns_main, str(src))
        if proj is not None:
            return proj
        if captured:
            return captured[-1]

        raise RuntimeError(
            f"No pylogiccircuit.Project or Circuit found when executing {src.name}. "
            "Define a top-level `project = Project(...)` or a zero-argument `build_*()` function returning a Project."
        )
    finally:
        if added_sys_path:
            try:
                sys.path.remove(src_dir)
            except ValueError:
                pass


def _select_circuit(project: Project, circuit_name: Optional[str]) -> Circuit:
    if circuit_name:
        return project.get_circuit(circuit_name)
    if project.main_circuit_id:
        for c in project.circuits:
            if c.circuit_id == project.main_circuit_id:
                return c
    if project.circuits:
        return project.circuits[-1]
    raise RuntimeError("Project contains no circuits.")


def render_once(
    source_path: Union[str, Path],
    png_path: Union[str, Path],
    *,
    circuit_name: Optional[str] = None,
    md_path: Optional[Union[str, Path]] = None,
    scale: int = 16,
    max_tt_inputs: int = 5,
    max_tt_rows: int = 32,
) -> RenderSnapshot:
    """Execute/load ``source_path``, verify, simulate, and atomically write preview output(s)."""
    src = Path(source_path).resolve()
    out_png = Path(png_path).resolve()
    out_md = Path(md_path).resolve() if md_path is not None else None
    ts = datetime.now().strftime("%H:%M:%S")

    try:
        project = load_project_from_source(src)
        circuit = _select_circuit(project, circuit_name)

        ver = circuit.verify(allow_diagonal=(src.suffix.lower() == ".circuitproject"))

        # Atomic PNG write via temp file in same directory
        tmp_png = out_png.with_name(f".{out_png.stem}.tmp.{os.getpid()}.png")
        render_circuit_png(circuit, tmp_png, scale=scale)
        os.replace(tmp_png, out_png)

        n_in = sum(1 for p in circuit.pins if p.pin_type == "Input")
        n_out = sum(1 for p in circuit.pins if p.pin_type == "Output")

        tt_md: Optional[str] = None
        oscillated = False
        if 0 < n_in <= max_tt_inputs and n_out > 0:
            sim = Simulator.from_project(project)
            tt = sim.truth_table(circuit.name, max_rows=max_tt_rows)
            tt_md = tt.format_markdown()
            oscillated = tt.oscillated

        snap = RenderSnapshot(
            ok=ver.ok and not oscillated,
            timestamp=ts,
            source_path=src,
            png_path=out_png,
            md_path=out_md,
            circuit_name=circuit.name,
            verify_errors=tuple(ver.errors),
            n_inputs=n_in,
            n_outputs=n_out,
            n_symbols=len(circuit.symbols),
            n_wires=len(circuit.wires),
            truth_table_md=tt_md,
            oscillated=oscillated,
        )

        if out_md is not None:
            _write_markdown_report(snap, out_md)
        return snap

    except Exception as exc:
        tb_short = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        _render_error_png(out_png, src.name, tb_short)
        snap = RenderSnapshot(
            ok=False,
            timestamp=ts,
            source_path=src,
            png_path=out_png,
            md_path=out_md,
            error=tb_short,
        )
        if out_md is not None:
            _write_markdown_report(snap, out_md)
        return snap


def _write_markdown_report(snap: RenderSnapshot, md_path: Path) -> None:
    try:
        rel_png = os.path.relpath(snap.png_path, md_path.parent)
    except ValueError:
        rel_png = str(snap.png_path)
    rel_png = rel_png.replace("\\", "/")

    lines: List[str] = [
        f"# Live Preview — `{snap.circuit_name or snap.source_path.name}`",
        "",
        f"Updated at `{snap.timestamp}` from `{snap.source_path.name}`",
        "",
    ]
    if snap.error:
        lines.extend([
            "> **Build Error**",
            "",
            "```text",
            snap.error,
            "```",
            "",
        ])
    else:
        status = "PASS" if snap.ok else "WARNING"
        lines.extend([
            f"**Status:** `{status}` · **Inputs:** `{snap.n_inputs}` · **Outputs:** `{snap.n_outputs}` · "
            f"**Symbols:** `{snap.n_symbols}` · **Wires:** `{snap.n_wires}`",
            "",
            f"![{snap.circuit_name}]({rel_png})",
            "",
        ])
        if snap.verify_errors:
            lines.append("## Verification Errors")
            lines.append("")
            for err in snap.verify_errors:
                lines.append(f"- {err}")
            lines.append("")
        if snap.truth_table_md:
            lines.append("## Truth Table")
            lines.append("")
            lines.append(snap.truth_table_md)
            lines.append("")

    _atomic_write_text(md_path, "\n".join(lines))


# ----------------------------------------------------------------------
# Optional zero-dependency live web server (--serve)
# ----------------------------------------------------------------------
_LIVE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>pylogiccircuit — Live Preview</title>
<style>
  body { margin: 0; background: #0f172a; color: #e2e8f0; font-family: system-ui, -apple-system, sans-serif; }
  header { display: flex; justify-content: space-between; align-items: center; padding: 10px 18px; background: #1e293b; border-bottom: 1px solid #334155; }
  .badge { font-family: monospace; font-size: 13px; color: #94a3b8; }
  main { display: flex; justify-content: center; padding: 20px; }
  img { max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 10px 30px rgba(0,0,0,0.45); background: #fff; }
</style>
</head>
<body>
  <header>
    <div><strong>pylogiccircuit</strong> · Live Preview</div>
    <div id="status" class="badge">Connecting…</div>
  </header>
  <main>
    <img id="preview" src="/preview.png" alt="Circuit Preview" />
  </main>
  <script>
    let lastVersion = -1;
    async function poll() {
      try {
        const res = await fetch('/status.json', { cache: 'no-store' });
        const data = await res.json();
        if (data.version !== lastVersion) {
          lastVersion = data.version;
          document.getElementById('preview').src = '/preview.png?v=' + data.version;
          const st = data.ok ? 'OK' : 'ERROR';
          document.getElementById('status').textContent = `${data.circuit || data.source} · ${st} · ${data.timestamp}`;
        }
      } catch (_) {}
      setTimeout(poll, 350);
    }
    poll();
  </script>
</body>
</html>
"""


class _PreviewState:
    def __init__(self, png_path: Path) -> None:
        self.png_path = png_path
        self.version = 0
        self.lock = threading.Lock()
        self.meta: Dict[str, Any] = {"version": 0, "ok": True, "circuit": "", "source": "", "timestamp": ""}

    def update(self, snap: RenderSnapshot) -> None:
        with self.lock:
            self.version += 1
            self.meta = {
                "version": self.version,
                "ok": snap.ok,
                "circuit": snap.circuit_name or "",
                "source": snap.source_path.name,
                "timestamp": snap.timestamp,
                "error": snap.error,
            }


def start_preview_server(state: _PreviewState, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    """Start a lightweight background HTTP server serving the live PNG preview."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                body = _LIVE_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif path == "/status.json":
                with state.lock:
                    body = json.dumps(state.meta).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif path == "/preview.png":
                if state.png_path.exists():
                    body = state.png_path.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_error(404)
            else:
                self.send_error(404)

    server = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def watch_file(
    source_path: Union[str, Path],
    png_path: Union[str, Path],
    *,
    circuit_name: Optional[str] = None,
    md_path: Optional[Union[str, Path]] = None,
    scale: int = 16,
    interval: float = 0.25,
    serve_port: Optional[int] = None,
    once: bool = False,
) -> int:
    """Watch ``source_path`` and re-render preview PNG (and optional Markdown) on every save."""
    src = Path(source_path).resolve()
    out_png = Path(png_path).resolve()
    state = _PreviewState(out_png)
    server: Optional[ThreadingHTTPServer] = None

    if serve_port is not None and not once:
        server = start_preview_server(state, port=serve_port)
        print(f"[pylogiccircuit] Live web preview at http://127.0.0.1:{serve_port}/")

    def _run_and_report() -> RenderSnapshot:
        snap = render_once(
            src,
            out_png,
            circuit_name=circuit_name,
            md_path=md_path,
            scale=scale,
        )
        state.update(snap)
        if snap.error:
            print(f"[{snap.timestamp}] ERROR: {snap.error}", flush=True)
        else:
            status = "OK" if snap.ok else "WARN"
            extra = f" + {snap.md_path.name}" if snap.md_path else ""
            print(
                f"[{snap.timestamp}] [{status}] {snap.circuit_name} -> {out_png.name}{extra} "
                f"(syms={snap.n_symbols}, wires={snap.n_wires})",
                flush=True,
            )
            for err in snap.verify_errors:
                print(f"    ! {err}", flush=True)
            if snap.oscillated:
                print("    ! Oscillation detected in truth table.", flush=True)
        return snap

    snap = _run_and_report()
    if once:
        return 0 if snap.error is None else 1

    print(
        f"[pylogiccircuit] Watching {src.name} (open {out_png.name} in a Zed split pane; Ctrl+C to stop)...",
        flush=True,
    )

    last_sig: Optional[Tuple[int, int]] = None
    try:
        st = src.stat()
        last_sig = (st.st_mtime_ns, st.st_size)
    except OSError:
        pass

    try:
        while True:
            time.sleep(interval)
            try:
                st = src.stat()
                sig = (st.st_mtime_ns, st.st_size)
            except OSError:
                continue
            if sig != last_sig:
                last_sig = sig
                _run_and_report()
    except KeyboardInterrupt:
        print("\n[pylogiccircuit] Watch stopped.")
        return 0
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
