"""Load and validate the house definition from YAML."""

from pathlib import Path

import yaml

from heat_pump_modelling.models import House

_DEFAULT_HOUSE_PATH = Path(__file__).parent.parent.parent / "data" / "house.yaml"


def load_house(path: str | Path | None = None) -> House:
    """Load a House from a YAML file.

    Args:
        path: Path to the YAML file. Defaults to data/house.yaml.

    Returns:
        Validated House model.
    """
    yaml_path = Path(path) if path is not None else _DEFAULT_HOUSE_PATH
    with yaml_path.open() as f:
        data = yaml.safe_load(f)
    return House.model_validate(data)
