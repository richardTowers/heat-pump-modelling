"""Builder for notebooks/phase0_visualisations.ipynb.

Run once to (re)generate the notebook from these cell definitions, then it is
executed with nbconvert. Kept in the repo so the notebook is reproducible from
source rather than hand-edited JSON. Safe to delete if it gets in the way.
"""

from pathlib import Path

import nbformat as nbf

nb = nbf.v4.new_notebook()
cells = []


def md(text):
    cells.append(nbf.v4.new_markdown_cell(text.strip("\n")))


def code(text):
    cells.append(nbf.v4.new_code_cell(text.strip("\n")))


md(r"""
# Phase 0 — what the inputs look like

Phase 0 left us with two real artefacts worth *seeing* before we compute
anything in Phase 1:

1. **The London weather** (Heathrow TMYx, 8760 hourly rows) — genuine data, so
   these plots won't be redone later. They also build the muscles Phase 1 and
   Phase 4 rely on: design temperature, hours-below-threshold, binning.
2. **The house definition** — *all dimensions are `PLACEHOLDER`*, so the house
   plots here are deliberately **schematic / structural**. They exist to
   sanity-check that `house.yaml` matches the real building, not to report
   numbers. We intentionally stop short of multiplying area × U-value — that is
   the fabric heat loss, and it belongs to Phase 1.

Outputs are saved as interactive HTML into `reports/`.
""")

code(r"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

from heat_pump_modelling.house import load_house
from heat_pump_modelling.models import Adjacency
from heat_pump_modelling.weather import load_london_epw

# Emit BOTH the plotly mimetype and a CDN-backed HTML fallback:
#   - "plotly_mimetype" -> application/vnd.plotly.v1+json, which PyCharm, VS Code
#     and JupyterLab render with their own bundled plotly.js;
#   - "notebook_connected" -> a <div>+RequireJS-from-CDN <script> for classic
#     Jupyter (and avoids embedding a ~3 MB plotly.js copy per figure).
# Using only the connected renderer leaves PyCharm blank — it runs the cell but
# never executes the CDN script, and without the mimetype it has nothing to draw.
pio.renderers.default = "plotly_mimetype+notebook_connected"

REPORTS = Path("..") / "reports"
REPORTS.mkdir(exist_ok=True)

# Saved HTML likewise references plotly.js from the CDN to stay tiny in git.
HTML_KW = dict(include_plotlyjs="cdn")

# London design external temperature (BS EN 12831-1 Annex NA), used as a
# reference line throughout — Phase 1 will size to this.
DESIGN_TEMP_C = -2.0
""")

md(r"""
## 1. London weather

`coerce_year=2021` just pins the TMYx rows onto one calendar year so the
DatetimeIndex is contiguous; the data is a *typical* year stitched from
2011–2025, not 2021 specifically.
""")

code(r"""
weather, meta = load_london_epw(coerce_year=2021)
temp = weather["temp_air"]

print(f"{meta['city']}  ({meta['latitude']:.3f}, {meta['longitude']:.3f})")
print(f"{len(weather)} hourly rows: {weather.index[0]:%Y-%m-%d} -> {weather.index[-1]:%Y-%m-%d}")
print(f"dry-bulb temp: min {temp.min():.1f}  mean {temp.mean():.1f}  max {temp.max():.1f} degC")
print(f"hours at or below design temp ({DESIGN_TEMP_C:g} degC): {(temp <= DESIGN_TEMP_C).sum()}")
""")

md(r"""
### 1a. Annual carpet plot

Hour-of-day (vertical) × day-of-year (horizontal), coloured by dry-bulb
temperature. This is the canonical way to take in a whole year at a glance: you
can read the seasons left-to-right and the daily warm-afternoon band top-to-bottom.
""")

code(r"""
carpet = pd.DataFrame({
    "temp": temp.values,
    "hour": temp.index.hour,
    "doy": temp.index.dayofyear,
})
grid = carpet.pivot_table(index="hour", columns="doy", values="temp")

# Month boundaries for nicer x ticks.
month_starts = pd.date_range("2021-01-01", "2021-12-01", freq="MS")
tickvals = month_starts.dayofyear
ticktext = month_starts.strftime("%b")

fig_carpet = go.Figure(
    go.Heatmap(
        z=grid.values,
        x=grid.columns,
        y=grid.index,
        colorscale="RdBu_r",
        zmid=temp.mean(),
        colorbar=dict(title="degC"),
        hovertemplate="day %{x}, %{y}:00<br>%{z:.1f} degC<extra></extra>",
    )
)
fig_carpet.update_layout(
    title="London Heathrow TMYx — hourly dry-bulb temperature",
    xaxis=dict(title="month", tickvals=tickvals, ticktext=ticktext),
    yaxis=dict(title="hour of day", dtick=6),
    height=420,
)
fig_carpet.write_html(REPORTS / "weather_carpet.html", **HTML_KW)
fig_carpet
""")

md(r"""
### 1b. Temperature duration curve

Every hour of the year sorted from warmest to coldest. The **most useful** plot
here: the dashed line is the −2 °C design temperature, and where the curve drops
below it is the handful of hours Phase 1 sizes the heat loss against. The shape
of this curve is exactly what Phase 4's bin/degree-hour SCOP analysis integrates
over.
""")

code(r"""
sorted_temp = np.sort(temp.values)[::-1]
hours = np.arange(1, len(sorted_temp) + 1)
n_below = int((temp <= DESIGN_TEMP_C).sum())

fig_dur = go.Figure()
fig_dur.add_scatter(
    x=hours, y=sorted_temp, mode="lines", name="dry-bulb temp",
    hovertemplate="%{x} h warmer than %{y:.1f} degC<extra></extra>",
)
fig_dur.add_hline(
    y=DESIGN_TEMP_C, line_dash="dash", line_color="firebrick",
    annotation_text=f"design temp {DESIGN_TEMP_C:g} degC — {n_below} h/yr below",
    annotation_position="bottom right",
)
fig_dur.update_layout(
    title="Temperature duration curve — hours per year above each temperature",
    xaxis_title="hours of the year (sorted, warmest first)",
    yaxis_title="dry-bulb temperature (degC)",
    height=420,
)
fig_dur.write_html(REPORTS / "weather_duration_curve.html", **HTML_KW)
fig_dur
""")

md(r"""
### 1c. Monthly distribution

Box-per-month of dry-bulb temperature — the clearest "seasonal London" story,
showing both the median march through the year and the spread within each month.
""")

code(r"""
monthly = pd.DataFrame({
    "temp": temp.values,
    "month_num": temp.index.month,
    "month": temp.index.strftime("%b"),
})
order = monthly.sort_values("month_num")["month"].unique()

fig_month = px.box(
    monthly, x="month", y="temp", category_orders={"month": list(order)},
    color="month", color_discrete_sequence=px.colors.sequential.Turbo,
)
fig_month.add_hline(
    y=DESIGN_TEMP_C, line_dash="dash", line_color="firebrick",
    annotation_text=f"design temp {DESIGN_TEMP_C:g} degC",
)
fig_month.update_layout(
    title="Monthly dry-bulb temperature distribution — London Heathrow TMYx",
    xaxis_title="month", yaxis_title="dry-bulb temperature (degC)",
    showlegend=False, height=420,
)
fig_month.write_html(REPORTS / "weather_monthly_box.html", **HTML_KW)
fig_month
""")

md(r"""
## 2. The house — schematic only

**Caveat in bold:** every dimension in `house.yaml` is a `PLACEHOLDER`. The
figures below are diagrammatic — boxes are *not to scale* and positions are *not
surveyed*. They are here to eyeball whether the YAML's structure (rooms,
setpoints, which walls face outside) matches the real building.

The model has no explicit floor field, so we derive floor from the room name as
a notebook-level assumption (and print it, so it's transparent). Worth
considering a `floor` field on `Room` later.
""")

code(r"""
house = load_house()

def floor_of(room):
    n = room.name.lower()
    return 1 if ("bedroom" in n or "bathroom" in n) else 0

for r in house.rooms:
    print(f"floor {floor_of(r)}: {r.name}  ({r.setpoint_c:g} degC, {r.floor_area_m2:g} m2)")

print(f"\ntotal floor area {house.total_floor_area_m2:g} m2, volume {house.total_volume_m3:g} m3")
""")

md(r"""
### 2a. Schematic floor layout

Two floors stacked; each room a box whose **width is proportional to floor area**
and whose **fill colour is its setpoint** (cooler→warmer). Each box lists its
setpoint, area, and the compass directions that face outdoors — a quick read on
where the heat losses will concentrate in Phase 1.
""")

code(r"""
import plotly.colors as pc

rooms = house.rooms
setpoints = [r.setpoint_c for r in rooms]
smin, smax = min(setpoints), max(setpoints)

def setpoint_color(sp):
    frac = 0.5 if smax == smin else (sp - smin) / (smax - smin)
    return pc.sample_colorscale("YlOrRd", 0.15 + 0.7 * frac)[0]

WIDTH_SCALE = 0.5   # m2 -> diagram units
ROOM_H = 1.0
FLOOR_GAP = 0.5
PAD = 0.15

fig_house = go.Figure()
floor_y = {0: 0.0, 1: ROOM_H + FLOOR_GAP}
cursor = {0: 0.0, 1: 0.0}

for r in rooms:
    f = floor_of(r)
    w = max(r.floor_area_m2 * WIDTH_SCALE, 2.0)
    x0, y0 = cursor[f], floor_y[f]
    x1, y1 = x0 + w, y0 + ROOM_H
    cursor[f] = x1 + PAD

    fig_house.add_shape(
        type="rect", x0=x0, y0=y0, x1=x1, y1=y1,
        line=dict(color="#444", width=1.5),
        fillcolor=setpoint_color(r.setpoint_c),
    )

    ext_orients = sorted({
        s.orientation for s in r.surfaces
        if s.adjacency == Adjacency.EXTERNAL and s.orientation
    })
    ext_txt = ("faces " + ", ".join(ext_orients)) if ext_orients else "no external walls"
    fig_house.add_annotation(
        x=(x0 + x1) / 2, y=(y0 + y1) / 2, showarrow=False,
        align="center", font=dict(size=11),
        text=(f"<b>{r.name}</b><br>{r.setpoint_c:g} degC · {r.floor_area_m2:g} m2"
              f"<br><span style='font-size:9px'>{ext_txt}</span>"),
    )

for f, label in [(0, "Ground floor"), (1, "First floor")]:
    fig_house.add_annotation(
        x=-0.5, y=floor_y[f] + ROOM_H / 2, showarrow=False,
        text=f"<b>{label}</b>", textangle=-90, font=dict(size=12, color="#666"),
    )

fig_house.update_layout(
    title="House schematic — boxes sized by floor area, coloured by setpoint (NOT to scale)",
    xaxis=dict(visible=False),
    yaxis=dict(visible=False, scaleanchor="x", scaleratio=1),
    plot_bgcolor="white", height=420,
    margin=dict(l=60, r=20, t=60, b=20),
)
fig_house.write_html(REPORTS / "house_schematic.html", **HTML_KW)
fig_house
""")

md(r"""
### 2b. Fabric makeup by adjacency

Surface **area** (m², not heat loss) per room, split by what each surface
borders. This shows the structure of the fabric model — how much external wall
vs party wall vs ground floor each room carries — without yet attaching
U-values. Party and internal areas are inert for heat loss; external, ground and
unheated are where Phase 1 will act.
""")

code(r"""
recs = [
    {"room": r.name, "adjacency": s.adjacency.value, "area": s.area_m2}
    for r in house.rooms for s in r.surfaces
]
fabric = (
    pd.DataFrame(recs)
    .groupby(["room", "adjacency"], as_index=False)["area"].sum()
)
room_order = [r.name for r in house.rooms][::-1]   # top-to-bottom as in YAML

fig_fabric = px.bar(
    fabric, x="area", y="room", color="adjacency", orientation="h",
    category_orders={"room": room_order},
    color_discrete_map={
        "external": "#d62728", "ground": "#8c564b", "unheated": "#ff7f0e",
        "party": "#7f7f7f", "internal": "#c7c7c7",
    },
)
fig_fabric.update_layout(
    title="Surface area by adjacency (structural — no U-values applied)",
    xaxis_title="surface area (m2)", yaxis_title="",
    legend_title="borders", height=420,
)
fig_fabric.write_html(REPORTS / "house_fabric_makeup.html", **HTML_KW)
fig_fabric
""")

md(r"""
## Saved outputs

All five figures are written to `reports/` as standalone interactive HTML:

- `weather_carpet.html` — annual temperature carpet
- `weather_duration_curve.html` — temperature duration curve + design temp
- `weather_monthly_box.html` — monthly temperature distribution
- `house_schematic.html` — schematic floor layout
- `house_fabric_makeup.html` — surface area by adjacency

**Next:** Phase 1 turns the fabric makeup into actual heat loss by attaching the
U-values from `data/u_values.yaml` and the design ΔT this weather sets.
""")

nb.cells = cells
nb.metadata["kernelspec"] = {
    "display_name": "Python 3", "language": "python", "name": "python3",
}

out = Path(__file__).parent / "phase0_visualisations.ipynb"
nbf.write(nb, out)
print(f"wrote {out}")
