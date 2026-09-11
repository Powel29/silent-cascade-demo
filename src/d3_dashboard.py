"""D3 — fake "all green" monitoring dashboard mock.

Writes outputs/d3_dashboard.html. This is a MOCK, not a working tool — we say so on the
slide. Open it in a browser and screenshot manually at 1600px wide -> outputs/d3_dashboard.png
(no headless-screenshot library is in requirements.txt, so this step stays manual).
"""

from __future__ import annotations

import random
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = REPO_ROOT / "outputs"

METRICS = [
    ("Uptime", "99.98%"),
    ("p50 Latency", "187ms"),
    ("Error rate", "0.01%"),
    ("Requests/min", "1,240"),
]

SERVICES = [
    "intake-api",
    "language-normaliser",
    "classifier",
    "urgency-scorer",
    "router",
    "queue-worker",
]


def sparkline_svg(seed: int, width: int = 160, height: int = 40) -> str:
    """A flat-ish random walk sparkline. Deterministic per card via `seed`."""
    rng = random.Random(seed)
    n = 24
    y = 20.0
    points = []
    for i in range(n):
        y += rng.uniform(-1.5, 1.5)
        y = max(4.0, min(height - 4.0, y))
        x = (i / (n - 1)) * width
        points.append(f"{x:.1f},{y:.1f}")
    path = " ".join(points)
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<polyline points="{path}" fill="none" stroke="#34a853" stroke-width="2"/>'
        f"</svg>"
    )


def build_html(seed: int = 42) -> str:
    metric_cards = "\n".join(
        f"""
        <div class="card">
          <div class="metric-label">{label}</div>
          <div class="metric-value">{value} <span class="dot green"></span></div>
          <div class="sparkline">{sparkline_svg(seed + i)}</div>
        </div>
        """
        for i, (label, value) in enumerate(METRICS)
    )

    service_rows = "\n".join(
        f"""
        <div class="service-row">
          <span class="dot green"></span>
          <span class="service-name">{name}</span>
          <span class="service-status">operational</span>
        </div>
        """
        for name in SERVICES
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CivicOps Monitor</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: #0f1216;
    color: #e8eaed;
    font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
    padding: 32px 40px;
  }}
  h1 {{
    font-size: 22px;
    font-weight: 600;
    margin: 0 0 4px 0;
  }}
  .subtitle {{
    color: #9aa0a6;
    font-size: 13px;
    margin-bottom: 28px;
  }}
  .cards {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 20px;
    margin-bottom: 32px;
  }}
  .card {{
    background: #171b21;
    border: 1px solid #262b33;
    border-radius: 10px;
    padding: 18px 20px;
  }}
  .metric-label {{
    color: #9aa0a6;
    font-size: 13px;
    margin-bottom: 8px;
  }}
  .metric-value {{
    font-size: 26px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
  }}
  .dot {{
    width: 9px;
    height: 9px;
    border-radius: 50%;
    display: inline-block;
  }}
  .dot.green {{ background: #34a853; box-shadow: 0 0 6px #34a85399; }}
  .panel {{
    background: #171b21;
    border: 1px solid #262b33;
    border-radius: 10px;
    padding: 8px 20px;
  }}
  .panel h2 {{
    font-size: 15px;
    font-weight: 600;
    color: #cfd2d6;
    margin: 14px 0;
  }}
  .service-row {{
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 4px;
    border-top: 1px solid #23272e;
    font-size: 14px;
  }}
  .service-row:first-of-type {{ border-top: none; }}
  .service-name {{ flex: 1; font-family: "SF Mono", Consolas, monospace; }}
  .service-status {{ color: #34a853; font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; }}
</style>
</head>
<body>
  <h1>CivicOps Monitor</h1>
  <div class="subtitle">Municipal grievance pipeline &middot; all systems &middot; last updated just now</div>

  <div class="cards">
    {metric_cards}
  </div>

  <div class="panel">
    <h2>Services</h2>
    {service_rows}
  </div>
</body>
</html>
"""


def main() -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    html = build_html(seed=42)
    out_path = OUTPUTS_DIR / "d3_dashboard.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"[d3_dashboard] wrote {out_path}")
    print(
        "[d3_dashboard] MOCK ONLY — no real telemetry backs this page. "
        "Open it in a browser, resize to 1600px wide, and screenshot manually to "
        "outputs/d3_dashboard.png (no screenshot library is in requirements.txt)."
    )


if __name__ == "__main__":
    main()
