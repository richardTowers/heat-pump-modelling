"""Entry point — summarise the house, its design heat loss, and the weather."""

from heat_pump_modelling.heat_loss import compute_house_heat_loss
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
    heat_loss = compute_house_heat_loss(house)
    cond = heat_loss.conditions
    print(f"Design heat loss (BS EN 12831-1, external {cond.external_temp_c:g} °C):")
    print(f"  {'room':<25}{'fabric':>8}{'vent':>8}{'total':>8}{'W/m²':>8}")
    for room in heat_loss.rooms:
        print(f"  {room.name:<25}{room.transmission_w:7.0f}W{room.ventilation_w:7.0f}W"
              f"{room.total_w:7.0f}W{room.specific_heat_loss_w_per_m2:7.0f} ")
    print(f"  {'WHOLE HOUSE':<25}{heat_loss.total_transmission_w:7.0f}W"
          f"{heat_loss.total_ventilation_w:7.0f}W{heat_loss.total_w:7.0f}W"
          f"{heat_loss.specific_heat_loss_w_per_m2:7.0f} ")
    print(f"  Heat loss coefficient: {heat_loss.total_coefficient_w_per_k:.1f} W/K")

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
