"""EPW weather file loader.

Wraps pvlib.iotools.read_epw with a convenience function for the bundled
London Heathrow TMYx file.

Data source:
    climate.onebuilding.org — WMO Region 6 / GBR / ENG_England
    File: GBR_ENG_London-Heathrow.Intl.AP.037720_TMYx.2011-2025.zip
    Coverage: 2011-2025 typical meteorological year
    Retrieved: 2026-06-11
"""

from pathlib import Path

import pandas as pd
import pvlib

_LONDON_EPW = (
    Path(__file__).parent.parent.parent
    / "data"
    / "weather"
    / "GBR_ENG_London-Heathrow.Intl.AP.037720_TMYx.2011-2025.epw"
)


def load_london_epw(coerce_year: int | None = None) -> tuple[pd.DataFrame, dict]:
    """Load the bundled London Heathrow TMYx 2011-2025 EPW file.

    Args:
        coerce_year: If given, overwrite the year field in all rows (useful
            for aligning with other annual time-series).

    Returns:
        (weather_df, metadata) — same as pvlib.iotools.read_epw.
        weather_df has a DatetimeIndex and columns including:
            temp_air [°C], temp_dew [°C], relative_humidity [%],
            ghi, dni, dhi [W/m²], wind_speed [m/s], wind_direction [°].
    """
    return pvlib.iotools.read_epw(str(_LONDON_EPW), coerce_year=coerce_year)


def load_epw(path: str | Path, coerce_year: int | None = None) -> tuple[pd.DataFrame, dict]:
    """Load any EPW file.

    Args:
        path: Path to the .epw file.
        coerce_year: If given, overwrite the year field in all rows.

    Returns:
        (weather_df, metadata) — same as pvlib.iotools.read_epw.
    """
    return pvlib.iotools.read_epw(str(path), coerce_year=coerce_year)
