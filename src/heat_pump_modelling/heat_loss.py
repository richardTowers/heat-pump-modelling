"""Steady-state design heat loss, BS EN 12831-1:2017 style.

Computes the room-by-room and whole-house design heat load at the winter
design condition. Two components per room:

    Φ_HL,i = Φ_T,i (transmission / fabric)  +  Φ_V,i (ventilation / infiltration)

We deliberately omit the EN 12831 heat-up power Φ_RH (extra capacity to recover
from a setback in intermittently heated buildings). This is a steady-state,
continuous-heating estimate — the appropriate basis for sizing a heat pump,
which is run continuously at low flow temperature rather than in boiler-style
bursts.

Transmission — temperature-adjustment-factor form (EN 12831-1 §6.3.2)
---------------------------------------------------------------------
For room i with internal design temperature θ_int,i and external design
temperature θ_e::

    Φ_T,i = (θ_int,i − θ_e) · Σ_k [ A_k · U_k · f_k ]

``f_k`` is the dimensionless **temperature adjustment factor** for element k —
the fraction of the full indoor↔outdoor ΔT that actually drives heat through
that element, given what it borders. This is where the party-wall and
ground-floor treatment is made explicit:

    external   f = 1.0    full ΔT to outside air
    party      f = 0.0    adjacent dwelling assumed heated to θ_int → no loss
                          (EN 12831-1 §6.3.3.2; the convention for terraced
                          housing — we do NOT claim credit for a warm neighbour,
                          we simply assume no net flow across the shared wall)
    internal   f = 0.0    adjacent heated room at the same setpoint
    unheated   f = b_u    loft / buffer space, partially tempered (default 0.9
                          for a ventilated cold loft; EN 12831-1 Annex)
    ground     f = (θ_int − θ_grnd) / (θ_int − θ_e)
                          heat flows to the stable deep-ground temperature
                          θ_grnd, not to the (colder) design air temperature

The ground treatment is the EN 12831 **simplified** steady form: a constant
mean ground temperature θ_grnd (≈ the site annual-mean air temperature). The
full ISO 13370 periodic ground-coupling method (slab perimeter/area B′,
edge-insulation, seasonal lag) is deliberately deferred — it would change the
ground-floor figure by a modest amount and adds a lot of geometry input. The
simplification is flagged on ``DesignConditions.ground_temp_c``.

Note the algebra: with f_ground substituted in, ``A·U·f·(θ_int − θ_e)`` reduces
to ``A·U·(θ_int − θ_grnd)`` — i.e. the factor is just bookkeeping that lets
every element share one ΔT while still losing heat to its real boundary.

Ventilation — simplified infiltration form (EN 12831-1 §6.3.3)
-------------------------------------------------------------
    Φ_V,i = ρ·c_p · n_i · V_i · (θ_int,i − θ_e)

``ρ·c_p`` of air ≈ 0.34 Wh/(m³·K). ``n_i`` is the room air change rate [1/h];
in a leaky, uninsulated, solid-wall house the design air change is
infiltration-dominated. Defaults by room type follow the MIS 3005-D / CIBSE
design air-change tables (see ``DesignConditions.default_air_change_rates``);
a surveyed value can be pinned per room via ``Room.air_change_rate_per_h``.
"""

from pydantic import BaseModel, Field

from heat_pump_modelling.models import Adjacency, House, Room, Surface, SurfaceType

# ρ·c_p of air [Wh/(m³·K)] — EN 12831-1 ventilation constant.
AIR_HEAT_CAPACITY_WH_PER_M3K = 0.34


class DesignConditions(BaseModel):
    """Design-condition assumptions shared across every room.

    All values carry a documented default for this London Victorian terrace;
    pass an instance to override (e.g. a colder design day, or a measured loft
    temperature factor).
    """

    external_temp_c: float = Field(
        default=-2.0,
        description="Winter design external temperature [°C]. London: −2 °C "
        "(BS EN 12831-1 National Annex / CIBSE).",
    )
    ground_temp_c: float = Field(
        default=10.0,
        description="Assumed mean ground temperature [°C] ≈ site annual-mean "
        "air temp. SIMPLIFICATION of the ISO 13370 periodic method.",
    )
    unheated_factor: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="b_u for surfaces bordering an unheated space (e.g. a "
        "ventilated cold loft). 1.0 = as cold as outside; EN 12831-1 Annex.",
    )
    default_air_change_rates: dict[str, float] = Field(
        default={
            "reception": 1.5,
            "living": 1.5,
            "lounge": 1.5,
            "kitchen": 2.0,
            "diner": 2.0,
            "bathroom": 3.0,
            "bedroom": 1.0,
            "hall": 2.0,
            "landing": 2.0,
            "default": 1.5,
        },
        description="Fallback design air change rates [1/h] keyed by a "
        "case-insensitive substring of the room name (MIS 3005-D / CIBSE "
        "tables for older, leaky dwellings). 'default' is used if none match.",
    )

    def air_change_rate_for(self, room: Room) -> float:
        """Resolve a room's design air change rate [1/h].

        A value pinned on the room (from survey) wins; otherwise the first
        room-type keyword found in the room name selects from the default
        table, falling back to ``default``.
        """
        if room.air_change_rate_per_h is not None:
            return room.air_change_rate_per_h
        name = room.name.lower()
        for keyword, rate in self.default_air_change_rates.items():
            if keyword != "default" and keyword in name:
                return rate
        return self.default_air_change_rates["default"]


def temperature_adjustment_factor(
    adjacency: Adjacency, room_setpoint_c: float, conditions: DesignConditions
) -> float:
    """Temperature adjustment factor f_k for an element of the given adjacency.

    See the module docstring for the per-adjacency rationale. The ground factor
    is clamped at 0 so that, at design, a room whose setpoint is below the
    ground temperature is never modelled as *gaining* heat through the floor
    (design heat loss conservatively ignores gains).
    """
    if adjacency is Adjacency.EXTERNAL:
        return 1.0
    if adjacency in (Adjacency.PARTY, Adjacency.INTERNAL):
        return 0.0
    if adjacency is Adjacency.UNHEATED:
        return conditions.unheated_factor
    if adjacency is Adjacency.GROUND:
        delta_t_ext = room_setpoint_c - conditions.external_temp_c
        if delta_t_ext <= 0:
            return 0.0
        return max(0.0, (room_setpoint_c - conditions.ground_temp_c) / delta_t_ext)
    raise ValueError(f"Unhandled adjacency: {adjacency!r}")


class SurfaceHeatLoss(BaseModel):
    """Transmission heat loss through one surface at the design condition."""

    name: str
    surface_type: SurfaceType
    adjacency: Adjacency
    area_m2: float
    u_value_w_per_m2k: float
    temperature_factor: float
    delta_t_k: float = Field(description="Room ΔT to external air [K]")
    heat_loss_coefficient_w_per_k: float = Field(description="A·U·f [W/K]")
    heat_loss_w: float = Field(description="A·U·f·ΔT [W]")


class RoomHeatLoss(BaseModel):
    """Design heat loss for one room: fabric (per-surface) + ventilation."""

    name: str
    setpoint_c: float
    floor_area_m2: float
    volume_m3: float
    air_change_rate_per_h: float
    delta_t_k: float
    surfaces: list[SurfaceHeatLoss]
    ventilation_coefficient_w_per_k: float = Field(description="ρ·c_p·n·V [W/K]")
    ventilation_w: float = Field(description="ρ·c_p·n·V·ΔT [W]")

    @property
    def transmission_coefficient_w_per_k(self) -> float:
        return sum(s.heat_loss_coefficient_w_per_k for s in self.surfaces)

    @property
    def transmission_w(self) -> float:
        return sum(s.heat_loss_w for s in self.surfaces)

    @property
    def total_coefficient_w_per_k(self) -> float:
        """Whole-room heat loss coefficient [W/K] = fabric + ventilation."""
        return self.transmission_coefficient_w_per_k + self.ventilation_coefficient_w_per_k

    @property
    def total_w(self) -> float:
        """Total design heat loss for the room [W]."""
        return self.transmission_w + self.ventilation_w

    @property
    def specific_heat_loss_w_per_m2(self) -> float:
        """Design heat loss per unit floor area [W/m²]."""
        return self.total_w / self.floor_area_m2


class HouseHeatLoss(BaseModel):
    """Whole-house design heat loss, aggregated from per-room results."""

    name: str
    conditions: DesignConditions
    rooms: list[RoomHeatLoss]

    @property
    def total_transmission_w(self) -> float:
        return sum(r.transmission_w for r in self.rooms)

    @property
    def total_ventilation_w(self) -> float:
        return sum(r.ventilation_w for r in self.rooms)

    @property
    def total_w(self) -> float:
        """Whole-house design heat load [W]."""
        return sum(r.total_w for r in self.rooms)

    @property
    def total_coefficient_w_per_k(self) -> float:
        """Building heat loss coefficient [W/K] (fabric + ventilation).

        Well-defined even though rooms have different ΔT — it is the sum of the
        per-room coefficients. ``total_w`` is the ΔT-weighted sum, not this × a
        single ΔT.
        """
        return sum(r.total_coefficient_w_per_k for r in self.rooms)

    @property
    def total_floor_area_m2(self) -> float:
        return sum(r.floor_area_m2 for r in self.rooms)

    @property
    def specific_heat_loss_w_per_m2(self) -> float:
        """Whole-house design heat loss per unit floor area [W/m²].

        The headline 'how hard does this house leak' number; MCS-style.
        """
        return self.total_w / self.total_floor_area_m2


def compute_surface_heat_loss(
    surface: Surface, room_setpoint_c: float, conditions: DesignConditions
) -> SurfaceHeatLoss:
    """Transmission heat loss through a single surface at design conditions."""
    delta_t = room_setpoint_c - conditions.external_temp_c
    f = temperature_adjustment_factor(surface.adjacency, room_setpoint_c, conditions)
    coefficient = surface.area_m2 * surface.u_value_w_per_m2k * f
    return SurfaceHeatLoss(
        name=surface.name,
        surface_type=surface.surface_type,
        adjacency=surface.adjacency,
        area_m2=surface.area_m2,
        u_value_w_per_m2k=surface.u_value_w_per_m2k,
        temperature_factor=f,
        delta_t_k=delta_t,
        heat_loss_coefficient_w_per_k=coefficient,
        heat_loss_w=coefficient * delta_t,
    )


def compute_room_heat_loss(room: Room, conditions: DesignConditions) -> RoomHeatLoss:
    """Fabric + ventilation design heat loss for one room."""
    delta_t = room.setpoint_c - conditions.external_temp_c
    surfaces = [compute_surface_heat_loss(s, room.setpoint_c, conditions) for s in room.surfaces]

    ach = conditions.air_change_rate_for(room)
    vent_coefficient = AIR_HEAT_CAPACITY_WH_PER_M3K * ach * room.volume_m3
    return RoomHeatLoss(
        name=room.name,
        setpoint_c=room.setpoint_c,
        floor_area_m2=room.floor_area_m2,
        volume_m3=room.volume_m3,
        air_change_rate_per_h=ach,
        delta_t_k=delta_t,
        surfaces=surfaces,
        ventilation_coefficient_w_per_k=vent_coefficient,
        ventilation_w=vent_coefficient * delta_t,
    )


def compute_house_heat_loss(
    house: House, conditions: DesignConditions | None = None
) -> HouseHeatLoss:
    """Whole-house design heat loss (BS EN 12831-1 steady-state).

    Args:
        house: Validated building definition.
        conditions: Design assumptions; defaults to the London Victorian-terrace
            ``DesignConditions``.

    Returns:
        ``HouseHeatLoss`` with per-room and per-surface breakdowns and
        whole-house totals / specific heat loss.
    """
    conditions = conditions or DesignConditions()
    rooms = [compute_room_heat_loss(r, conditions) for r in house.rooms]
    return HouseHeatLoss(name=house.name, conditions=conditions, rooms=rooms)
