"""Entry point — print a summary of the house definition and weather file."""

from heat_pump_modelling.house import load_house
from heat_pump_modelling.weather import load_london_epw


def main() -> None:
    house = load_house()
    print(f"House: {house.name}")
    print(f"  Rooms:            {len(house.rooms)}")
    print(f"  Total floor area: {house.total_floor_area_m2:.1f} m²")
    print(f"  Total volume:     {house.total_volume_m3:.1f} m³")
    print()
    for room in house.rooms:
        n_surf = len(room.surfaces)
        n_rad = len(room.radiators)
        print(f"  {room.name:<25} {room.floor_area_m2:5.1f} m²  "
              f"{n_surf} surfaces  {n_rad} radiators")

    print()
    weather, meta = load_london_epw()
    print(f"Weather: {meta['city']}, {meta['country']}")
    print(f"  Latitude:  {meta['latitude']:.2f}°")
    print(f"  Longitude: {meta['longitude']:.2f}°")
    print(f"  Altitude:  {meta['altitude']} m")
    print(f"  Rows:      {len(weather)} hours")
    t_min = weather["temp_air"].min()
    t_max = weather["temp_air"].max()
    print(f"  Temp range: {t_min:.1f} °C to {t_max:.1f} °C")


if __name__ == "__main__":
    main()
