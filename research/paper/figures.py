"""Figures for the working paper, from the committed error logs.

    python -m research.paper.figures

Writes research/paper/figures/*.svg and the CSV behind each figure. Plain
SVG (no plotting library), so the figures render on GitHub and in the HTML
version of the paper.
"""

from pathlib import Path

import pandas as pd

from research.nowcast.backtest import common_sample

HERE = Path(__file__).resolve().parent
OUT = HERE / "figures"
ROOT = HERE.parent

SERIES = [
    ("attention", "Attention (Gate 2)", "#1f6f8b"),
    ("flights", "Flights (Gate 3)", "#c0781a"),
    ("survey", "Hotel survey (Gate 3)", "#9b3d5a"),
]
INK, MUTED, RULE, PAPER = "#1d2a2e", "#5b6a6e", "#d5dedd", "#ffffff"
FONT = "font-family:Helvetica,Arial,sans-serif"


def relative_mape(errors: pd.DataFrame, model: str, reference: str) -> dict[int, float]:
    """Per horizon: % change in MAPE of model vs reference on shared cells."""
    out = {}
    for h in range(1, 13):
        both = common_sample(errors[errors["h"] == h], (model, reference))
        mape = both.groupby("model")["ape"].mean()
        out[h] = 100 * (mape[model] / mape[reference] - 1)
    return out


def horizon_data() -> pd.DataFrame:
    gate2 = pd.read_csv(ROOT / "forecast/results/holdout_errors.csv")
    gate3 = pd.read_csv(ROOT / "gate3/results/holdout_errors.csv")
    return pd.DataFrame(
        {
            "attention": relative_mape(gate2, "POOL_GR_WG", "POOL_GR"),
            "flights": relative_mape(gate3, "WG_F", "WG"),
            "survey": relative_mape(gate3, "WG_S", "WG"),
        }
    ).rename_axis("h")


def country_data() -> pd.DataFrame:
    gate2 = pd.read_csv(ROOT / "forecast/results/holdout_verdict.csv").set_index("geo")
    gate3 = pd.read_csv(ROOT / "gate3/results/holdout_verdict.csv").set_index("geo")
    return pd.DataFrame(
        {
            "attention": gate2["ratio_attention"],
            "flights": gate3["WG_F"],
            "survey": gate3["WG_S"],
        }
    ).sort_values("attention")


def _svg(width: int, height: int, body: list[str], label: str) -> str:
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}" role="img" aria-label="{label}">',
            f'<rect width="{width}" height="{height}" fill="{PAPER}"/>',
            *body,
            "</svg>",
        ]
    )


def horizon_svg(data: pd.DataFrame) -> str:
    width, height = 720, 380
    left, right, top, bottom = 64, 190, 24, 56
    low, high = -6.0, 3.0
    x = lambda h: left + (h - 1) * (width - left - right) / 11  # noqa: E731
    y = lambda v: top + (high - v) * (height - top - bottom) / (high - low)  # noqa: E731
    body = []
    for tick in range(-6, 4, 1):
        body.append(
            f'<line x1="{left}" x2="{width - right}" y1="{y(tick):.1f}" y2="{y(tick):.1f}" '
            f'stroke="{INK if tick == 0 else RULE}" stroke-width="{1.2 if tick == 0 else 1}"/>'
        )
        body.append(
            f'<text x="{left - 8}" y="{y(tick) + 4:.1f}" text-anchor="end" font-size="12" '
            f'fill="{MUTED}" style="{FONT}">{tick:+d}%</text>'
        )
    for h in range(1, 13):
        body.append(
            f'<text x="{x(h):.1f}" y="{height - bottom + 20}" text-anchor="middle" '
            f'font-size="12" fill="{MUTED}" style="{FONT}">{h}</text>'
        )
    body.append(
        f'<text x="{(left + width - right) / 2:.1f}" y="{height - 12}" text-anchor="middle" '
        f'font-size="13" fill="{INK}" style="{FONT}">Forecast horizon (months ahead)</text>'
    )
    body.append(
        f'<text transform="translate(16 {(top + height - bottom) / 2:.1f}) rotate(-90)" '
        f'text-anchor="middle" font-size="13" fill="{INK}" style="{FONT}">'
        "Change in error (MAPE)</text>"
    )
    for index, (key, label, color) in enumerate(SERIES):
        points = " ".join(f"{x(h):.1f},{y(v):.1f}" for h, v in data[key].items())
        body.append(
            f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.4"/>'
        )
        for h, v in data[key].items():
            body.append(f'<circle cx="{x(h):.1f}" cy="{y(v):.1f}" r="3.2" fill="{color}"/>')
        ly = top + 18 + index * 24
        body.append(
            f'<line x1="{width - right + 16}" x2="{width - right + 40}" y1="{ly}" y2="{ly}" '
            f'stroke="{color}" stroke-width="2.4"/>'
        )
        body.append(
            f'<text x="{width - right + 46}" y="{ly + 4}" font-size="12" fill="{INK}" '
            f'style="{FONT}">{label}</text>'
        )
    body.append(
        f'<text x="{width - right + 16}" y="{top + 104}" font-size="11" fill="{MUTED}" '
        f'style="{FONT}">Below zero: the signal</text>'
    )
    body.append(
        f'<text x="{width - right + 16}" y="{top + 118}" font-size="11" fill="{MUTED}" '
        f'style="{FONT}">lowers forecast error.</text>'
    )
    return _svg(width, height, body, "Change in forecast error from each signal, by horizon")


def country_svg(data: pd.DataFrame) -> str:
    rows = list(data.index)
    width, row_h = 720, 20
    left, right, top = 56, 24, 44
    height = top + row_h * len(rows) + 48
    low, high = 0.70, 1.30
    x = lambda v: left + (min(max(v, low), high) - low) * (width - left - right) / (high - low)  # noqa: E731
    body = []
    for tick in (0.7, 0.8, 0.9, 0.97, 1.0, 1.1, 1.2, 1.3):
        stroke = INK if tick == 1.0 else RULE
        dash = ' stroke-dasharray="4 3"' if tick == 0.97 else ""
        body.append(
            f'<line x1="{x(tick):.1f}" x2="{x(tick):.1f}" y1="{top - 6}" '
            f'y2="{top + row_h * len(rows)}" stroke="{stroke}"{dash}/>'
        )
        body.append(
            f'<text x="{x(tick):.1f}" y="{top + row_h * len(rows) + 18}" text-anchor="middle" '
            f'font-size="11" fill="{MUTED}" style="{FONT}">{tick:g}</text>'
        )
    body.append(
        f'<text x="{(left + width - right) / 2:.1f}" y="{height - 8}" text-anchor="middle" '
        f'font-size="12" fill="{INK}" style="{FONT}">'
        "Error ratio with the signal to without it (below 1 = helps; dashed = 0.97 bar)</text>"
    )
    for index, (_, label, color) in enumerate(SERIES):
        lx = left + index * 210
        body.append(f'<circle cx="{lx + 6}" cy="18" r="5" fill="{color}"/>')
        body.append(
            f'<text x="{lx + 16}" y="22" font-size="12" fill="{INK}" style="{FONT}">{label}</text>'
        )
    for row, geo in enumerate(rows):
        cy = top + row_h * row + row_h / 2
        body.append(
            f'<text x="{left - 10}" y="{cy + 4:.1f}" text-anchor="end" font-size="11" '
            f'fill="{INK}" style="{FONT}">{geo}</text>'
        )
        for key, _, color in SERIES:
            value = data.loc[geo, key]
            if pd.notna(value):
                body.append(
                    f'<circle cx="{x(value):.1f}" cy="{cy:.1f}" r="4.2" fill="{color}" '
                    f'fill-opacity="0.85"/>'
                )
    return _svg(width, height, body, "Error ratios by country for each signal")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    horizons = horizon_data()
    countries = country_data()
    horizons.round(2).to_csv(OUT / "fig1_horizon.csv")
    countries.round(4).to_csv(OUT / "fig2_countries.csv")
    (OUT / "fig1_horizon.svg").write_text(horizon_svg(horizons))
    (OUT / "fig2_countries.svg").write_text(country_svg(countries))
    print(horizons.round(1).to_string())


if __name__ == "__main__":
    main()
