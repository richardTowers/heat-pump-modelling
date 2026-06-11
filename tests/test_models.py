"""Tests for the building data models and house loader."""

import pytest

from heat_pump_modelling.models import Adjacency, House, Radiator, Room, Surface, SurfaceType
from heat_pump_modelling.house import load_house


class TestSurface:
    def test_valid_external_wall(self):
        s = Surface(
            name="Front wall",
            surface_type=SurfaceType.WALL,
            area_m2=10.0,
            u_value_w_per_m2k=2.1,
            adjacency=Adjacency.EXTERNAL,
            orientation="N",
        )
        assert s.area_m2 == 10.0
        assert s.adjacency == Adjacency.EXTERNAL

    def test_area_must_be_positive(self):
        with pytest.raises(Exception):
            Surface(
                name="Bad surface",
                surface_type=SurfaceType.WALL,
                area_m2=-1.0,
                u_value_w_per_m2k=2.1,
                adjacency=Adjacency.EXTERNAL,
            )

    def test_u_value_cannot_be_negative(self):
        with pytest.raises(Exception):
            Surface(
                name="Bad surface",
                surface_type=SurfaceType.WALL,
                area_m2=10.0,
                u_value_w_per_m2k=-0.1,
                adjacency=Adjacency.EXTERNAL,
            )

    def test_party_wall_zero_u_value_allowed(self):
        s = Surface(
            name="Party wall",
            surface_type=SurfaceType.WALL,
            area_m2=8.0,
            u_value_w_per_m2k=0.0,
            adjacency=Adjacency.PARTY,
        )
        assert s.u_value_w_per_m2k == 0.0


class TestRoom:
    def test_volume(self):
        room = Room(
            name="Test room",
            floor_area_m2=20.0,
            ceiling_height_m=2.5,
            setpoint_c=21.0,
        )
        assert room.volume_m3 == pytest.approx(50.0)

    def test_room_with_surfaces(self):
        surface = Surface(
            name="Wall",
            surface_type=SurfaceType.WALL,
            area_m2=5.0,
            u_value_w_per_m2k=1.9,
            adjacency=Adjacency.EXTERNAL,
        )
        room = Room(
            name="Room",
            floor_area_m2=15.0,
            ceiling_height_m=2.7,
            setpoint_c=21.0,
            surfaces=[surface],
        )
        assert len(room.surfaces) == 1


class TestHouse:
    def test_total_floor_area(self):
        rooms = [
            Room(name="Room A", floor_area_m2=10.0, ceiling_height_m=2.5, setpoint_c=21.0),
            Room(name="Room B", floor_area_m2=15.0, ceiling_height_m=2.5, setpoint_c=18.0),
        ]
        house = House(name="Test house", rooms=rooms)
        assert house.total_floor_area_m2 == pytest.approx(25.0)

    def test_total_volume(self):
        rooms = [
            Room(name="Room A", floor_area_m2=10.0, ceiling_height_m=2.5, setpoint_c=21.0),
            Room(name="Room B", floor_area_m2=15.0, ceiling_height_m=3.0, setpoint_c=18.0),
        ]
        house = House(name="Test house", rooms=rooms)
        assert house.total_volume_m3 == pytest.approx(10 * 2.5 + 15 * 3.0)


class TestLoadHouse:
    def test_loads_default_house(self):
        house = load_house()
        assert house.name == "Victorian mid-terrace"
        assert len(house.rooms) > 0

    def test_all_rooms_have_surfaces(self):
        house = load_house()
        for room in house.rooms:
            assert len(room.surfaces) > 0, f"Room '{room.name}' has no surfaces"

    def test_heated_rooms_have_radiators(self):
        house = load_house()
        heated_rooms = [r for r in house.rooms if r.setpoint_c >= 21.0]
        for room in heated_rooms:
            assert len(room.radiators) > 0, f"Heated room '{room.name}' has no radiators"

    def test_floor_areas_positive(self):
        house = load_house()
        for room in house.rooms:
            assert room.floor_area_m2 > 0

    def test_total_floor_area_plausible(self):
        house = load_house()
        # Victorian mid-terrace should be between 60 and 120 m²
        assert 60 < house.total_floor_area_m2 < 120

    def test_radiator_outputs_positive(self):
        house = load_house()
        for room in house.rooms:
            for rad in room.radiators:
                assert rad.rated_output_w > 0
