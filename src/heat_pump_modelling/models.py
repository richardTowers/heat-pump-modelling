"""Pydantic data models for the building definition.

Hierarchy: House → Room → Surface / Radiator / PipeSegment

Units are kept explicit in field names throughout. All temperatures in °C,
areas in m², lengths in m or mm as noted, power in W, U-values in W/m²K.
"""

from enum import Enum

from pydantic import BaseModel, Field


class Adjacency(str, Enum):
    """What a surface borders — determines whether it contributes to heat loss."""

    EXTERNAL = "external"   # outdoor air
    PARTY = "party"         # neighbouring heated dwelling (Θadj ≈ Θint per EN 12831)
    GROUND = "ground"       # ground (requires ISO 13370 / EN 12831 ground-floor method)
    UNHEATED = "unheated"   # unheated buffer space (loft, garage, cellar)
    INTERNAL = "internal"   # adjacent heated room at same setpoint — no heat loss


class SurfaceType(str, Enum):
    WALL = "wall"
    WINDOW = "window"
    DOOR = "door"
    FLOOR = "floor"
    ROOF = "roof"


class Surface(BaseModel):
    """A thermally homogeneous building element.

    U-values from CIBSE Guide A or measured; see data/u_values.yaml for sources.
    """

    name: str
    surface_type: SurfaceType
    area_m2: float = Field(gt=0, description="Net area (excluding window/door openings) [m²]")
    u_value_w_per_m2k: float = Field(ge=0, description="Thermal transmittance [W/m²K]")
    adjacency: Adjacency
    orientation: str | None = None  # compass bearing: N, NE, E, SE, S, SW, W, NW


class Radiator(BaseModel):
    """Radiator defined by its EN 442 rated output.

    EN 442 standard test conditions: flow 75 °C, return 65 °C, room 20 °C → ΔT₅₀ = 50 K.
    Actual output at other conditions: Q = Q_rated × (ΔT / 50)^n, n ≈ 1.3.
    """

    name: str
    rated_output_w: float = Field(gt=0, description="EN 442 output at ΔT₅₀ [W]")
    height_mm: int | None = None
    length_mm: int | None = None


class PipeSegment(BaseModel):
    """A straight run of pipework."""

    name: str
    diameter_mm: float = Field(gt=0)
    length_m: float = Field(gt=0)
    insulated: bool = False


class Room(BaseModel):
    """A thermally distinct zone.

    Setpoint follows MIS 3005-D Table 1 defaults:
    living rooms 21 °C, bedrooms 18 °C, bathrooms 22 °C.
    """

    name: str
    floor_area_m2: float = Field(gt=0)
    ceiling_height_m: float = Field(gt=0)
    setpoint_c: float = Field(description="Design internal temperature [°C]")
    air_change_rate_per_h: float | None = Field(
        default=None,
        ge=0,
        description="Design air change rate [1/h]. If None, resolved from a "
        "room-type default table at heat-loss time (see DesignConditions).",
    )
    surfaces: list[Surface] = []
    radiators: list[Radiator] = []
    pipe_segments: list[PipeSegment] = []

    @property
    def volume_m3(self) -> float:
        return self.floor_area_m2 * self.ceiling_height_m


class House(BaseModel):
    """The complete building definition."""

    name: str
    location: str = ""
    rooms: list[Room] = []

    @property
    def total_floor_area_m2(self) -> float:
        return sum(r.floor_area_m2 for r in self.rooms)

    @property
    def total_volume_m3(self) -> float:
        return sum(r.volume_m3 for r in self.rooms)
