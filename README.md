# Heat pump retrofit model — Victorian mid-terrace

A learning project exploring the modelling stack behind UK heat pump design
software: from MCS-style steady-state calculations up to dynamic
thermal–hydraulic simulation, using my own house as the test case.

The aim is to learn the relevant **libraries and frameworks**, not to write
numerical solvers from scratch. Visualisations are a first-class deliverable
at every phase.

## The test case

- Victorian mid-terrace house, London
- Solid brick walls (uninsulated), suspended timber ground floor, party walls both sides
- Gas combi boiler + radiators (mixed sizes/ages, pipework to be surveyed)
- A dehumidifier in regular use (moisture matters — solid walls)
- No smart meter, so only very coarse gas / electricity consumption data available (historic meter readings)

## Domain context

- **MCS 031** (Heat Pump Pre-Sale Information and Performance Calculation,
  v4.0, mandatory since March 2025): the consumer-facing annual performance
  estimate. Uses specific heat loss (W/m²) + system type + an SPF lookup
  table from the Heat Emitter Guide. It is *not* a design tool.
- **MIS 3005-D**: the design standard. Heat pump selection must be based on
  a room-by-room heat loss calculation per **BS EN 12831-1:2017**.
- Radiator output follows EN 442: output ∝ ΔT^n, n ≈ 1.3.
- Commercial tools to be aware of (and roughly emulate): Heatpunk,
  Heat Engineer, the MCS Excel tools.

## Tooling decisions

- Python 3.12, managed with **uv** (`uv sync`; deps in `pyproject.toml`)
- Dev container already set up (uv feature, ruff, jupyter)
- Core libraries by phase (add as needed, don't preinstall everything):
  pandas, numpy, scipy, pydantic, plotly | CoolProp, fluids, ht,
  pandapipes | hplib, TESPy | psychrolib | networkx
- Weather: hourly EPW file for London (CIBSE/IWEC-style), read via pvlib
  or ladybug
- Phase 5 will introduce **OpenModelica + IBPSA/Buildings library** driven
  from Python via FMU export (`fmpy`). Do NOT hand-roll DAE solvers; the
  one exception is the deliberately simple RC model in Phase 5a.
- Notebooks for exploration; promote stable code into a `src/` package with
  tests (pytest).

## Architecture

Inputs (geometry, U-values, weather) → 1. fabric heat loss → 2. emitter sizing → 3. hydraulics → 4. heat pump model → 5.
dynamic simulation ← calibration against measured gas data; 6. MCS 031 estimate sits on top of (1); 7.
moisture/psychrometrics cross-cuts.

## TODO

### Phase 0 — project skeleton
- [x] `uv init`, `src/` layout, pytest, ruff config
- [x] Data model (pydantic) for the house: `Room`, `Surface` (wall/window/
      floor/roof, U-value, area, orientation, adjacency: external / party /
      ground / unheated), `Radiator`, `PipeSegment`
- [x] House definition as data (YAML or Python) with placeholder dimensions
      to be replaced by a real survey; U-value lookup table with sources
      (CIBSE Guide A typical values for solid brick, single/double glazing,
      suspended floor)
- [x] Fetch/commit a London hourly EPW weather file + loader

### Phase 1 — steady-state heat loss (BS EN 12831 style)
- [ ] Room-by-room fabric + ventilation heat loss at design conditions
      (London design external temp ≈ −2 °C, per-room internal setpoints)
- [ ] Party wall and ground floor treatment made explicit and documented
- [ ] Whole-house total, specific heat loss (W/m²)
- [ ] Viz: Plotly Sankey of heat flows by element; per-room bar chart
- [ ] Tests: hand-checked reference room

### Phase 2 — MCS 031 estimate layer
- [ ] Implement the MCS 031 v4.0 methodology from the published standard
      (SPF lookup by system type + flow temp band; annual kWh and cost)
- [ ] Reproduce the warnings logic for potentially undersized radiators
- [ ] Compare output against the official MCS Excel tool for sanity

### Phase 3 — emitter analysis
- [ ] EN 442 radiator model: output(flow, return, room temp), n = 1.3
- [ ] For each room: max flow temp at which existing radiator meets Phase 1
      load; whole-house "weakest room" flow temperature
- [ ] Weather compensation curve model; seasonal coverage plot
- [ ] Viz: output vs flow temp curves per radiator, required-load overlay

### Phase 4 — heat pump performance
- [ ] hplib: pick 2–3 representative ASHPs; COP(source temp, sink temp)
- [ ] Compute SCOP against the EPW weather + compensation curve; compare
      with the MCS 031 table SPF
- [ ] Viz: COP heatmap over (outdoor temp × flow temp); bin analysis
- [ ] Stretch: TESPy refrigeration cycle model; log p–h diagram

### Phase 5 — dynamic simulation + calibration
- [ ] 5a: lumped RC model (ISO 13790/52016 5R1C style) in scipy, hourly,
      driven by EPW; explicit thermal mass for solid brick
- [ ] Calibrate heat loss coefficient against metered gas data
      (boiler efficiency assumption documented); compare with Phase 1
      bottom-up value and write up the discrepancy
- [ ] 5b: OpenModelica + IBPSA: zone + radiators + heat pump + control;
      export FMU, drive from Python with fmpy; compare against 5a
- [ ] Viz: simulated vs measured daily gas use; indoor temp traces

### Phase 6 — hydraulics
- [ ] Pipe network as graph (networkx); pandapipes (or fluids/ht) for
      pressure drop and flow distribution at heat-pump ΔT (5 K) vs boiler
      ΔT (20 K)
- [ ] Index circuit, pump curve intersection, lockshield balancing
- [ ] Flag undersized pipe runs (velocity/noise limits)
- [ ] Viz: network diagram, edges coloured by velocity or ΔT

### Phase 7 — moisture & the dehumidifier
- [ ] psychrolib: room moisture balance (generation, ventilation,
      dehumidifier extraction); surface condensation / mould risk on solid
      external walls (fRsi-style check)
- [ ] Compare continuous low-temp heating vs intermittent combi heating
      for surface temps and RH
- [ ] Viz: interactive psychrometric chart with room states plotted

### Stretch
- [ ] Streamlit/Dash app wrapping Phases 1–4 (a mini Heatpunk)
- [ ] Sensitivity analysis: wall insulation, glazing, airtightness vs
      required heat pump size and SCOP
- [ ] 3D modelling of the building in Blender, BIM

## Working notes for Claude Code

- Prefer well-maintained libraries over bespoke numerics (see tooling
  decisions). Cite the standard/equation source in docstrings.
- Keep physical units explicit (ideally with pint) — unit bugs are the
  classic failure mode in this domain.
- Each phase should end with: working code in `src/`, at least one test,
  and one saved visualisation in `reports/`.
- Real survey data (room dimensions, radiator sizes, pipe runs, gas
  readings) will be added incrementally; structure code so placeholder
  data is obvious and swappable.