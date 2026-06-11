"""Tests for the BS EN 12831-1 steady-state heat loss calculation.

The headline test is ``TestReferenceRoom`` — a deliberately simple room whose
transmission and ventilation losses are computed by hand in the comments and
asserted exactly. The remaining tests pin individual behaviours (the
temperature adjustment factors, the ventilation formula, whole-house
aggregation) so a regression points at a specific cause.
"""

import pytest

from heat_pump_modelling.heat_loss import (
    AIR_HEAT_CAPACITY_WH_PER_M3K,
    DesignConditions,
    compute_house_heat_loss,
    compute_room_heat_loss,
    temperature_adjustment_factor,
)
from heat_pump_modelling.models import Adjacency, House, Room, Surface, SurfaceType

# Default design conditions used for the hand calculations below.
COND = DesignConditions()  # external −2 °C, ground 10 °C, b_u 0.9


def _surface(area, u, adjacency, surface_type=SurfaceType.WALL):
    return Surface(
        name="s",
        surface_type=surface_type,
        area_m2=area,
        u_value_w_per_m2k=u,
        adjacency=adjacency,
    )


class TestTemperatureAdjustmentFactor:
    def test_external_is_one(self):
        assert temperature_adjustment_factor(Adjacency.EXTERNAL, 21.0, COND) == 1.0

    def test_party_and_internal_are_zero(self):
        assert temperature_adjustment_factor(Adjacency.PARTY, 21.0, COND) == 0.0
        assert temperature_adjustment_factor(Adjacency.INTERNAL, 21.0, COND) == 0.0

    def test_unheated_uses_b_u(self):
        assert temperature_adjustment_factor(Adjacency.UNHEATED, 18.0, COND) == COND.unheated_factor

    def test_ground_factor(self):
        # (θ_int − θ_grnd) / (θ_int − θ_e) = (21 − 10) / (21 − (−2)) = 11/23
        f = temperature_adjustment_factor(Adjacency.GROUND, 21.0, COND)
        assert f == pytest.approx(11.0 / 23.0)

    def test_ground_factor_clamped_non_negative(self):
        # Setpoint below the ground temperature must not become a heat gain.
        cold = DesignConditions(ground_temp_c=15.0)
        assert temperature_adjustment_factor(Adjacency.GROUND, 12.0, cold) == 0.0


class TestReferenceRoom:
    """A hand-checked room.

    Geometry: 10 m² floor, 2.5 m high → V = 25 m³. Setpoint 21 °C, external
    −2 °C → ΔT = 23 K. ACH pinned at 1.0 /h.

    Surfaces:
      external wall  A=10  U=2.0  f=1            → Q = 10·2.0·1·23      = 460.0 W
      window         A=2   U=5.0  f=1            → Q =  2·5.0·1·23      = 230.0 W
      ground floor   A=10  U=0.7  f=11/23        → Q = 10·0.7·(11/23)·23 = 77.0 W
      party wall     A=10  U=1.5  f=0            → Q = 0                 =   0.0 W
    Transmission                                 → 460 + 230 + 77        = 767.0 W

    Ventilation: 0.34 · 1.0 · 25 · 23                                    = 195.5 W
    Total                                        → 767 + 195.5           = 962.5 W
    Specific: 962.5 / 10                                                 = 96.25 W/m²
    """

    @pytest.fixture
    def room(self):
        return Room(
            name="Reference",
            floor_area_m2=10.0,
            ceiling_height_m=2.5,
            setpoint_c=21.0,
            air_change_rate_per_h=1.0,
            surfaces=[
                _surface(10.0, 2.0, Adjacency.EXTERNAL),
                _surface(2.0, 5.0, Adjacency.EXTERNAL, SurfaceType.WINDOW),
                _surface(10.0, 0.7, Adjacency.GROUND, SurfaceType.FLOOR),
                _surface(10.0, 1.5, Adjacency.PARTY),
            ],
        )

    def test_transmission(self, room):
        result = compute_room_heat_loss(room, COND)
        assert result.transmission_w == pytest.approx(767.0)

    def test_ventilation(self, room):
        result = compute_room_heat_loss(room, COND)
        assert result.ventilation_w == pytest.approx(195.5)

    def test_total(self, room):
        result = compute_room_heat_loss(room, COND)
        assert result.total_w == pytest.approx(962.5)

    def test_specific(self, room):
        result = compute_room_heat_loss(room, COND)
        assert result.specific_heat_loss_w_per_m2 == pytest.approx(96.25)

    def test_party_wall_contributes_nothing(self, room):
        result = compute_room_heat_loss(room, COND)
        party = next(s for s in result.surfaces if s.adjacency == Adjacency.PARTY)
        assert party.heat_loss_w == 0.0

    def test_ground_loss_equals_loss_to_ground_temp(self, room):
        # A·U·f·ΔT_ext should collapse to A·U·(θ_int − θ_grnd) = 10·0.7·11 = 77.
        result = compute_room_heat_loss(room, COND)
        floor = next(s for s in result.surfaces if s.adjacency == Adjacency.GROUND)
        assert floor.heat_loss_w == pytest.approx(10.0 * 0.7 * (21.0 - 10.0))


class TestVentilationConstant:
    def test_formula(self):
        room = Room(
            name="Box",
            floor_area_m2=20.0,
            ceiling_height_m=2.0,  # V = 40 m³
            setpoint_c=20.0,  # ΔT = 22 K
            air_change_rate_per_h=2.0,
        )
        result = compute_room_heat_loss(room, COND)
        expected = AIR_HEAT_CAPACITY_WH_PER_M3K * 2.0 * 40.0 * 22.0
        assert result.ventilation_w == pytest.approx(expected)


class TestAirChangeResolution:
    def test_pinned_value_wins(self):
        room = Room(
            name="Front bedroom",
            floor_area_m2=10.0,
            ceiling_height_m=2.5,
            setpoint_c=18.0,
            air_change_rate_per_h=0.5,
        )
        assert COND.air_change_rate_for(room) == 0.5

    def test_resolved_from_name(self):
        bathroom = Room(
            name="Bathroom", floor_area_m2=4.0, ceiling_height_m=2.5, setpoint_c=22.0
        )
        assert COND.air_change_rate_for(bathroom) == 3.0

    def test_falls_back_to_default(self):
        odd = Room(name="Snug", floor_area_m2=8.0, ceiling_height_m=2.5, setpoint_c=21.0)
        assert COND.air_change_rate_for(odd) == COND.default_air_change_rates["default"]


class TestWholeHouseAggregation:
    def test_totals_sum_rooms(self):
        rooms = [
            Room(
                name="A",
                floor_area_m2=10.0,
                ceiling_height_m=2.5,
                setpoint_c=21.0,
                air_change_rate_per_h=1.0,
                surfaces=[_surface(10.0, 2.0, Adjacency.EXTERNAL)],
            ),
            Room(
                name="B",
                floor_area_m2=10.0,
                ceiling_height_m=2.5,
                setpoint_c=18.0,
                air_change_rate_per_h=1.0,
                surfaces=[_surface(10.0, 2.0, Adjacency.EXTERNAL)],
            ),
        ]
        house = House(name="Two-room", rooms=rooms)
        result = compute_house_heat_loss(house, COND)

        per_room = [compute_room_heat_loss(r, COND) for r in rooms]
        assert result.total_w == pytest.approx(sum(r.total_w for r in per_room))
        assert result.total_transmission_w == pytest.approx(
            sum(r.transmission_w for r in per_room)
        )
        assert result.total_coefficient_w_per_k == pytest.approx(
            sum(r.total_coefficient_w_per_k for r in per_room)
        )

    def test_specific_heat_loss(self):
        house = House(
            name="One-room",
            rooms=[
                Room(
                    name="A",
                    floor_area_m2=10.0,
                    ceiling_height_m=2.5,
                    setpoint_c=21.0,
                    air_change_rate_per_h=1.0,
                    surfaces=[_surface(10.0, 2.0, Adjacency.EXTERNAL)],
                )
            ],
        )
        result = compute_house_heat_loss(house, COND)
        assert result.specific_heat_loss_w_per_m2 == pytest.approx(
            result.total_w / 10.0
        )


class TestRealHouse:
    def test_runs_and_is_plausible(self):
        from heat_pump_modelling.house import load_house

        result = compute_house_heat_loss(load_house())
        # A solid-wall Victorian terrace of ~70-90 m² should land in a few kW,
        # i.e. roughly 60-160 W/m² of design heat loss. Wide bounds — this is a
        # sanity guard against unit/sign errors, not a precise expectation.
        assert 60.0 < result.specific_heat_loss_w_per_m2 < 160.0
        assert result.total_w > 0
