"""Lay a Brief out as one self-contained HTML document, sized for A4.

No template engine and no external assets: the file opens offline and
prints to PDF from any browser. Charts are inline SVG drawn here.
"""

from html import escape

from tourism_pulse_api.briefs.build import MONTHS, Brief, Trend, format_value

INK = "#1b2a33"
MUTED = "#5d6b74"
ACCENT = "#0b6e75"
BAND = "#cfe6e8"
LEVEL_COLOURS = {"high": "#b3402e", "moderate": "#b07a12", "low": "#2f7d4f"}

CSS = f"""
@page {{ size: A4; margin: 18mm 16mm; }}
* {{ box-sizing: border-box; }}
body {{ font: 10.5pt/1.5 Georgia, 'Times New Roman', serif; color: {INK}; margin: 0 auto;
       max-width: 178mm; padding: 12mm 4mm; background: #fff; }}
h1, h2, h3, table, .meta, .tag, .note, figcaption {{ font-family: 'Helvetica Neue', Arial,
       sans-serif; }}
h1 {{ font-size: 25pt; line-height: 1.15; margin: 0 0 2mm; }}
h2 {{ font-size: 13.5pt; margin: 9mm 0 2mm; padding-top: 3mm; border-top: 1.5pt solid {INK};
     break-after: avoid; }}
p {{ margin: 0 0 2.5mm; }}
.kicker {{ font: 600 9pt 'Helvetica Neue', Arial, sans-serif; letter-spacing: .12em;
          text-transform: uppercase; color: {ACCENT}; }}
.meta, .note, figcaption {{ font-size: 8.5pt; color: {MUTED}; }}
.cover {{ padding-bottom: 2mm; }}
.score {{ display: flex; gap: 8mm; align-items: center; margin: 6mm 0 2mm; }}
.score b {{ font: 700 44pt/1 'Helvetica Neue', Arial, sans-serif; }}
.tag {{ display: inline-block; padding: .6mm 2.5mm; border-radius: 2mm; color: #fff;
       font-size: 8.5pt; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; }}
ol.findings {{ padding-left: 5mm; margin: 0; }}
ol.findings li {{ margin-bottom: 2mm; }}
table {{ width: 100%; border-collapse: collapse; font-size: 9pt; margin: 2mm 0 3mm; }}
th {{ text-align: left; font-weight: 600; color: {MUTED}; border-bottom: .75pt solid {INK};
     padding: 1.2mm 2mm 1.2mm 0; vertical-align: bottom; }}
td {{ border-bottom: .4pt solid #d5dbdf; padding: 1.4mm 2mm 1.4mm 0; vertical-align: top; }}
td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
tr.subject td {{ font-weight: 700; background: #f1f6f6; }}
figure {{ margin: 3mm 0; break-inside: avoid; }}
svg {{ display: block; width: 100%; height: auto; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 4mm 8mm; }}
section {{ break-inside: avoid-page; }}
@media screen and (max-width: 640px) {{ .grid {{ grid-template-columns: 1fr; }}
  .score b {{ font-size: 34pt; }} table {{ font-size: 8.5pt; }} }}
@media print {{ body {{ padding: 0; }} }}
"""


def _e(value: object) -> str:
    return escape(str(value))


def _percentile_bar(percentile: float) -> str:
    width = max(0.0, min(100.0, percentile))
    return (
        '<svg viewBox="0 0 100 6" role="img" preserveAspectRatio="none" style="height:3mm" '
        f'aria-label="{width:.0f}th percentile">'
        '<rect width="100" height="6" fill="#e6ebee"/>'
        f'<rect width="{width:.1f}" height="6" fill="{ACCENT}"/>'
        '<rect x="69.6" width=".8" height="6" fill="#fff"/></svg>'
    )


def _sparkline(trend: Trend) -> str:
    values = [value for _, value in trend.points]
    low, high = min(values), max(values)
    span = (high - low) or 1.0
    step = 200 / (len(values) - 1)
    points = " ".join(
        f"{i * step:.1f},{36 - 30 * (value - low) / span:.1f}" for i, value in enumerate(values)
    )
    return (
        f'<svg viewBox="-2 0 204 42" role="img" aria-label="{_e(trend.label)} by year">'
        f'<polyline points="{points}" fill="none" stroke="{ACCENT}" stroke-width="1.6"/>'
        f'<circle cx="200" cy="{36 - 30 * (values[-1] - low) / span:.1f}" r="2.4" '
        f'fill="{ACCENT}"/></svg>'
    )


def _season_chart(brief: Brief) -> str:
    season = brief.seasonality
    top = max(item.share for item in season.months)
    bars = []
    for i, item in enumerate(season.months):
        height = 70 * item.share / top
        fill = ACCENT if item.month == season.peak_month else "#8fb9bd"
        bars.append(
            f'<rect x="{i * 30 + 4}" y="{80 - height:.1f}" width="22" height="{height:.1f}" '
            f'fill="{fill}"/>'
            f'<text x="{i * 30 + 15}" y="92" text-anchor="middle" font-size="7" '
            f'fill="{MUTED}">{MONTHS[item.month - 1]}</text>'
            f'<text x="{i * 30 + 15}" y="{76 - height:.1f}" text-anchor="middle" font-size="6.5" '
            f'fill="{INK}">{item.share * 100:.0f}%</text>'
        )
    even = 80 - 70 * (1 / 12) / top
    return (
        '<svg viewBox="0 0 360 96" role="img" font-family="Arial, sans-serif" '
        'aria-label="Share of annual nights by month">'
        + "".join(bars)
        + f'<line x1="0" x2="360" y1="{even:.1f}" y2="{even:.1f}" stroke="{INK}" '
        'stroke-width=".6" stroke-dasharray="3 2"/></svg>'
    )


def _outlook_chart(outlook: dict) -> str:
    history = outlook["history"][-24:]
    points = outlook["points"]
    values = (
        [item["value"] for item in history]
        + [item["high_80"] for item in points]
        + [item["low_80"] for item in points]
    )
    low, high = min(values), max(values)
    span = (high - low) or 1.0
    total = len(history) + len(points)
    step = 350 / max(total - 1, 1)

    def y(value: float) -> float:
        return 104 - 92 * (value - low) / span

    past = " ".join(f"{i * step:.1f},{y(item['value']):.1f}" for i, item in enumerate(history))
    start = len(history)
    # Start the dashed line at the last official month so the two join.
    joint = [f"{(start - 1) * step:.1f},{y(history[-1]['value']):.1f}"] if history else []
    future = " ".join(
        joint
        + [f"{(start + i) * step:.1f},{y(item['point']):.1f}" for i, item in enumerate(points)]
    )
    upper = [f"{(start + i) * step:.1f},{y(item['high_80']):.1f}" for i, item in enumerate(points)]
    lower = [f"{(start + i) * step:.1f},{y(item['low_80']):.1f}" for i, item in enumerate(points)]
    labels = "".join(
        f'<text x="{index * step:.1f}" y="118" font-size="7" fill="{MUTED}" '
        f'text-anchor="{anchor}">{_e(label)}</text>'
        for index, label, anchor in (
            (0, history[0]["period"] if history else points[0]["period"], "start"),
            (start, points[0]["period"], "middle"),
            (total - 1, points[-1]["period"], "end"),
        )
    )
    return (
        '<svg viewBox="-4 0 358 122" role="img" font-family="Arial, sans-serif" '
        'aria-label="Monthly nights: history and outlook range">'
        f'<polygon points="{" ".join(upper + lower[::-1])}" fill="{BAND}"/>'
        f'<polyline points="{past}" fill="none" stroke="{INK}" stroke-width="1.3"/>'
        f'<polyline points="{future}" fill="none" stroke="{ACCENT}" stroke-width="1.6" '
        'stroke-dasharray="4 2"/>' + labels + "</svg>"
    )


def _cover(brief: Brief, licensee: str | None) -> str:
    pressure = brief.pressure
    region = ""
    score = ""
    if pressure is not None:
        region = (
            f"{_e(pressure.region_name or pressure.nuts_code)} "
            f"({_e(pressure.nuts_code)}, {_e(pressure.level_name)})"
        )
        colour = LEVEL_COLOURS.get(pressure.level or "", MUTED)
        rank = (
            f"Rank {brief.european_rank} of {brief.european_regions} European regions at this level"
            if brief.european_rank
            else ""
        )
        score = (
            f'<div class="score"><b>{pressure.score:.0f}</b><div>'
            f'<span class="tag" style="background:{colour}">{_e(pressure.level)} pressure</span>'
            f'<div class="meta">Tourism pressure score, 0 to 100<br>{rank}</div></div></div>'
        )
    holder = f" · Licensed to {_e(licensee)}" if licensee else ""
    return (
        '<header class="cover"><div class="kicker">Tourism Pulse · Destination Pressure Brief'
        f"</div><h1>{_e(brief.place_name)}</h1>"
        f'<div class="meta">{region}</div>{score}'
        f'<div class="meta">Issued {brief.generated_on.isoformat()}{holder}</div></header>'
    )


def _findings(brief: Brief) -> str:
    if not brief.findings:
        return ""
    items = "".join(f"<li>{_e(finding)}</li>" for finding in brief.findings)
    return f'<section><h2>Key findings</h2><ol class="findings">{items}</ol></section>'


def _pressure(brief: Brief) -> str:
    pressure = brief.pressure
    if pressure is None:
        return ""
    national = {rank.indicator: rank for rank in brief.national}

    def rows(readings) -> str:
        out = []
        for reading in readings:
            rank = national.get(reading.indicator)
            out.append(
                f"<tr><td><b>{_e(reading.label)}</b><div class='note'>{_e(reading.definition)}"
                f"</div></td><td class='num'>{format_value(reading.unit, reading.value)}</td>"
                f"<td class='num'>{reading.year}</td>"
                f"<td class='num'>{reading.rank} of {reading.peers}</td>"
                f"<td class='num'>{f'{rank.rank} of {rank.regions}' if rank else ''}</td>"
                f"<td style='width:26mm'>{_percentile_bar(reading.percentile)}"
                f"<div class='note'>{reading.percentile:.0f}th percentile</div></td></tr>"
            )
        return "".join(out)

    head = (
        "<tr><th>Indicator</th><th class='num'>Value</th><th class='num'>Year</th>"
        "<th class='num'>Rank in Europe</th><th class='num'>Rank in country</th>"
        "<th>Against Europe</th></tr>"
    )
    dependence = ""
    if pressure.dependence:
        dependence = (
            "<h2>Economic dependence</h2><p>Shown beside the pressure score and never part "
            "of it: how much of the regional economy sits in the sectors visitors use.</p>"
            f"<table>{head}{rows(pressure.dependence)}</table>"
        )
    return (
        "<section><h2>Where it stands in Europe</h2>"
        f"<p>{_e(pressure.method)} The white mark on each bar is the 70th percentile, where "
        f"high pressure starts.</p><table>{head}{rows(pressure.indicators)}</table></section>"
        f"<section>{dependence}</section>"
    )


def _peers(brief: Brief) -> str:
    if len(brief.peers) < 2:
        return ""
    rows = "".join(
        f"<tr{' class=subject' if row.is_subject else ''}><td class='num'>{row.rank}</td>"
        f"<td>{_e(row.name or row.nuts_code)}</td><td>{_e(row.nuts_code)}</td>"
        f"<td class='num'>{row.score:.0f}</td><td>{_e(row.level)}</td></tr>"
        for row in brief.peers
    )
    return (
        "<section><h2>Against the rest of the country</h2>"
        "<p>Regions of the same country at the same level, highest pressure first.</p>"
        "<table><tr><th class='num'>Rank</th><th>Region</th><th>Code</th>"
        f"<th class='num'>Score</th><th>Level</th></tr>{rows}</table></section>"
    )


def _trends(brief: Brief) -> str:
    if not brief.trends:
        return ""
    cells = []
    for trend in brief.trends:
        first_year, first = trend.points[0]
        last_year, last = trend.points[-1]
        change = f" ({trend.change * 100:+.0f}%)" if trend.change is not None else ""
        cells.append(
            f"<figure>{_sparkline(trend)}<figcaption><b>{_e(trend.label)}</b><br>"
            f"{format_value(trend.unit, first)} in {first_year} to "
            f"{format_value(trend.unit, last)} in {last_year}{change}</figcaption></figure>"
        )
    return f'<section><h2>How it has moved</h2><div class="grid">{"".join(cells)}</div></section>'


def _seasonality(brief: Brief) -> str:
    season = brief.seasonality
    if season is None:
        return ""
    return (
        "<section><h2>Seasonality</h2>"
        f"<figure>{_season_chart(brief)}<figcaption>Share of the year's official nights by "
        f"month, {_e(season.period)}. The dashed line is an even spread (8.3% a month). "
        f"Source: {_e(season.source)}.</figcaption></figure></section>"
    )


def _outlook(brief: Brief) -> str:
    outlook = brief.outlook
    if outlook is None:
        return ""
    rows = "".join(
        f"<tr><td>Next {item['months']} months</td>"
        f"<td class='num'>{item['forecast']:,.0f}</td>"
        f"<td class='num'>{item['low_80']:,.0f} to {item['high_80']:,.0f}</td>"
        f"<td class='num'>{item['last_year']:,.0f}</td>"
        f"<td class='num'>{item['change'] * 100:+.1f}%</td></tr>"
        for item in outlook["outlook"]
    )
    table = (
        "<table><tr><th>Window</th><th class='num'>Expected nights</th>"
        "<th class='num'>Range</th><th class='num'>Same months last year</th>"
        f"<th class='num'>Change</th></tr>{rows}</table>"
        if rows
        else ""
    )
    record = outlook.get("track_record")
    if record and record.get("scored"):
        track = (
            f"Of the forecasts published so far, {record['scored']} now have an official "
            f"figure: the average error is {record['mape'] * 100:.1f}% and "
            f"{record['coverage_80'] * 100:.0f}% fell inside the 80% range."
        )
    else:
        track = "None of the published forecasts for this place has an official figure yet."
    status = "" if outlook["validated"] else " <b>Not validated at this level.</b>"
    return (
        "<section><h2>Outlook for the next twelve months</h2>"
        f"<figure>{_outlook_chart(outlook)}<figcaption>Monthly official nights (solid), "
        f"the outlook (dashed) and its 80% range (shaded). Forecast origin "
        f"{_e(outlook['origin'])}.</figcaption></figure>{table}"
        f"<p class='note'>{_e(outlook['method'])}{status} {_e(track)} Every forecast batch is "
        "published before the months it covers, hashed and timestamped, in the public "
        "tourism-pulse-forecasts record, and is never revised.</p></section>"
    )


def _method(brief: Brief) -> str:
    limits = "".join(f"<li>{_e(limit)}</li>" for limit in brief.limits)
    sources = "".join(
        f"<tr><td>{_e(source.title)}</td><td>{_e(source.licence)}</td>"
        f"<td>{_e(source.attribution or '')}</td></tr>"
        for source in brief.sources
    )
    withheld = ""
    if brief.withheld:
        items = "".join(f"<li>{_e(item)}</li>" for item in brief.withheld)
        withheld = f"<p class='note'>Left out of this brief:</p><ul class='note'>{items}</ul>"
    return (
        f"<section><h2>What this brief does not say</h2><ul>{limits}</ul></section>"
        "<section><h2>Sources and reuse</h2>"
        "<table><tr><th>Source</th><th>Terms</th><th>Acknowledgement</th></tr>"
        f"{sources}</table>{withheld}"
        "<p class='note'>The licence holder may reproduce the figures, tables and charts of "
        'this brief in their own reports and proposals, with the credit "Tourism Pulse, from '
        'official statistics" and the source acknowledgements above. Figures are computed by '
        "Tourism Pulse from the named sources and are not those sources' own publications. "
        "No sentence in this brief was written by a language model.</p></section>"
    )


def render_html(brief: Brief, licensee: str | None = None) -> str:
    body = "".join(
        (
            _cover(brief, licensee),
            _findings(brief),
            _pressure(brief),
            _peers(brief),
            _trends(brief),
            _seasonality(brief),
            _outlook(brief),
            _method(brief),
        )
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{_e(brief.place_name)}: Destination Pressure Brief</title>"
        f"<style>{CSS}</style></head><body>{body}</body></html>"
    )
