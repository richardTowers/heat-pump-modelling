"""Builder for notebooks/phase1_heat_loss.ipynb.

Run once to (re)generate the notebook from these cell definitions, then it is
executed with nbconvert. Kept in the repo so the notebook is reproducible from
source rather than hand-edited JSON. Safe to delete if it gets in the way.

Mirrors notebooks/_build_phase0_viz.py.
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
# Phase 1 — steady-state design heat loss

Phase 0 stopped at surface *areas* split by what they border. Phase 1 attaches
the U-values and the design ΔT to turn that fabric makeup into **watts**, the
BS EN 12831-1 way:

$$
\Phi_{HL,i} = \underbrace{(\theta_{int,i}-\theta_e)\sum_k A_k U_k f_k}_{\text{transmission}}
\;+\; \underbrace{0.34\, n_i V_i (\theta_{int,i}-\theta_e)}_{\text{ventilation}}
$$

The temperature adjustment factor $f_k$ is where the **party-wall and
ground-floor treatment lives** (see `src/heat_pump_modelling/heat_loss.py`):

| borders | $f$ | meaning |
|---|---|---|
| external | 1.0 | full ΔT to outside air |
| party / internal | 0.0 | neighbour / next room at the same temp — no net flow |
| unheated (loft) | $b_u$ = 0.9 | partially tempered cold roof space |
| ground | $f_g$ | heat flows to stable ~10 °C ground, not −2 °C air |

where $f_g=(\theta_{int}-\theta_{grnd})/(\theta_{int}-\theta_e)$ ≈ 0.48 for a 21 °C room.

**Caveat unchanged from Phase 0:** every dimension in `house.yaml` is a
`PLACEHOLDER`. These watts are therefore *structurally* correct but
*numerically* provisional — they move when the survey lands. The point of the
plots is to see where the heat goes and whether the split looks sane.

Outputs are saved as interactive HTML into `reports/`.
""")

code(r"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

from heat_pump_modelling.heat_loss import DesignConditions, compute_house_heat_loss
from heat_pump_modelling.house import load_house
from heat_pump_modelling.models import Adjacency, SurfaceType

# Same dual-renderer setup as Phase 0: a plotly mimetype for PyCharm/VS Code
# plus a CDN-backed HTML fallback for classic Jupyter. See the Phase 0 notebook
# for the full rationale.
pio.renderers.default = "plotly_mimetype+notebook_connected"

REPORTS = Path("..") / "reports"
REPORTS.mkdir(exist_ok=True)
HTML_KW = dict(include_plotlyjs="cdn")

conditions = DesignConditions()
house = load_house()
result = compute_house_heat_loss(house, conditions)

print(f"Design external temp: {conditions.external_temp_c:g} degC   "
      f"ground: {conditions.ground_temp_c:g} degC   loft b_u: {conditions.unheated_factor:g}")
print(f"Whole-house design heat loss: {result.total_w:,.0f} W  "
      f"(fabric {result.total_transmission_w:,.0f} "
      f"+ ventilation {result.total_ventilation_w:,.0f})")
print(f"Heat loss coefficient: {result.total_coefficient_w_per_k:.1f} W/K")
print(f"Specific heat loss: {result.specific_heat_loss_w_per_m2:.1f} W/m2 "
      f"over {result.total_floor_area_m2:.1f} m2")
""")

md(r"""
## Where the heat goes — element categories

Every loss-bearing surface is bucketed into one of six categories. Party and
internal surfaces carry no loss (f = 0) and are dropped. Ventilation is treated
as its own category so the fabric-vs-air split is visible everywhere below.
""")

code(r"""
# Map (surface_type, adjacency) -> a human element category + a stable colour.
CATEGORY_COLOURS = {
    "External wall": "#d62728",
    "Window":        "#1f77b4",
    "Door":          "#9467bd",
    "Roof (loft)":   "#ff7f0e",
    "Ground floor":  "#8c564b",
    "Ventilation":   "#2ca02c",
}

def element_category(surface):
    if surface.surface_type == SurfaceType.WINDOW:
        return "Window"
    if surface.surface_type == SurfaceType.DOOR:
        return "Door"
    if surface.adjacency == Adjacency.GROUND:
        return "Ground floor"
    if surface.adjacency == Adjacency.UNHEATED:
        return "Roof (loft)"
    return "External wall"

# Long-form table: one row per (room, category) with summed watts.
rows = []
for room in result.rooms:
    for s in room.surfaces:
        if s.heat_loss_w > 0:
            rows.append({
                "room": room.name,
                "category": element_category(s),
                "watts": s.heat_loss_w,
            })
    rows.append({"room": room.name, "category": "Ventilation", "watts": room.ventilation_w})

flows = pd.DataFrame(rows).groupby(["room", "category"], as_index=False)["watts"].sum()
by_category = flows.groupby("category")["watts"].sum().sort_values(ascending=False)
print(by_category.round(0).astype(int).to_string())
""")

md(r"""
### 1. Sankey — element → room → whole-house load

The required Phase 1 Sankey. Read it left-to-right: each **element category**
(left) feeds the **rooms** it occurs in (middle), and every room feeds the
single **whole-house design load** node (right). Band thickness is watts, so you
can trace, e.g., how much of the total is windows, and which room dominates.
""")

code(r"""
categories = list(by_category.index)
rooms = [r.name for r in result.rooms]
total_label = f"Design load\n{result.total_w:,.0f} W"

# Node index layout: [categories..., rooms..., total]
node_labels = categories + rooms + [total_label]
cat_idx = {c: i for i, c in enumerate(categories)}
room_idx = {r: len(categories) + i for i, r in enumerate(rooms)}
total_idx = len(node_labels) - 1

node_colours = (
    [CATEGORY_COLOURS[c] for c in categories]
    + ["#bcbd22"] * len(rooms)
    + ["#444444"]
)

src, tgt, val, link_colour = [], [], [], []

def rgba(hex_colour, alpha=0.45):
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"

# element category -> room
for _, row in flows.iterrows():
    src.append(cat_idx[row["category"]])
    tgt.append(room_idx[row["room"]])
    val.append(row["watts"])
    link_colour.append(rgba(CATEGORY_COLOURS[row["category"]]))

# room -> total
for room in result.rooms:
    src.append(room_idx[room.name])
    tgt.append(total_idx)
    val.append(room.total_w)
    link_colour.append("rgba(120,120,120,0.35)")

fig_sankey = go.Figure(go.Sankey(
    arrangement="snap",
    node=dict(
        label=node_labels, color=node_colours, pad=14, thickness=16,
        line=dict(color="#888", width=0.5),
        hovertemplate="%{label}<br>%{value:.0f} W<extra></extra>",
    ),
    link=dict(
        source=src, target=tgt, value=val, color=link_colour,
        hovertemplate="%{source.label} → %{target.label}<br>%{value:.0f} W<extra></extra>",
    ),
))
fig_sankey.update_layout(
    title=f"Design heat loss flows — element → room → whole house "
          f"({result.total_w:,.0f} W total)",
    font_size=11, height=520,
)
fig_sankey.write_html(REPORTS / "heat_loss_sankey.html", **HTML_KW)
fig_sankey
""")

md(r"""
### 2. Per-room heat loss, stacked by element

The required Phase 1 bar chart. Each bar is a room's total design load, stacked
by element category so the fabric-vs-ventilation and wall-vs-window splits are
legible per room. The dashed markers show **specific** heat loss (W/m²) on the
right axis — a small high-ventilation bathroom can lose a lot per m² even when
its absolute watts are modest.
""")

code(r"""
room_order = [r.name for r in result.rooms]
cat_order = [c for c in CATEGORY_COLOURS if c in set(flows["category"])]

fig_bar = px.bar(
    flows, x="room", y="watts", color="category",
    category_orders={"room": room_order, "category": cat_order},
    color_discrete_map=CATEGORY_COLOURS,
)
fig_bar.update_traces(hovertemplate="%{x}<br>%{fullData.name}: %{y:.0f} W<extra></extra>")

specific = [r.specific_heat_loss_w_per_m2 for r in result.rooms]
fig_bar.add_scatter(
    x=room_order, y=specific, name="specific (W/m²)", yaxis="y2",
    mode="markers", marker=dict(symbol="diamond", size=11, color="#222"),
    hovertemplate="%{x}<br>%{y:.0f} W/m²<extra></extra>",
)
fig_bar.update_layout(
    title="Design heat loss by room, stacked by element",
    xaxis_title="", yaxis_title="design heat loss (W)",
    yaxis2=dict(title="specific (W/m²)", overlaying="y", side="right",
                showgrid=False, rangemode="tozero"),
    legend_title="element", height=460, barmode="stack",
)
fig_bar.write_html(REPORTS / "heat_loss_by_room.html", **HTML_KW)
fig_bar
""")

md(r"""
## Saved outputs

Two figures written to `reports/` as standalone interactive HTML:

- `heat_loss_sankey.html` — element → room → whole-house heat flows
- `heat_loss_by_room.html` — per-room load stacked by element, + specific W/m²

The whole-house headline (design load at −2 °C, specific W/m²) is printed in the
first code cell above. All figures remain provisional until the survey replaces
the `PLACEHOLDER` dimensions.

**Next:** Phase 2 puts the MCS 031 estimate layer on top of this; Phase 3 asks
whether each room's existing radiator can actually deliver its Phase 1 load at a
heat-pump-friendly flow temperature.
""")

nb.cells = cells
nb.metadata["kernelspec"] = {
    "display_name": "Python 3", "language": "python", "name": "python3",
}

out = Path(__file__).parent / "phase1_heat_loss.ipynb"
nbf.write(nb, out)
print(f"wrote {out}")
