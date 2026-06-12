"""Headless recalc of the MCS spreadsheet, behind one small interface.

``recalc(file, inputs, outputs)`` writes ``inputs`` into the named cells,
recalculates, and returns the requested ``outputs`` as a ``{ref: value}`` dict,
where each ref is ``"<Sheet>!<A1>"``. ``None`` means the cell evaluates to an
error.

Two interchangeable engines:

* :func:`formulas_recalc` -- the pure-Python ``formulas`` engine, in-process,
  with the vendored :mod:`tests.mcs_oracle.formulas_patch` LOOKUP fix. Fast and
  dependency-light; the **default everyday oracle** (``recalc``).
* :func:`lo_recalc` -- headless LibreOffice via UNO
  (:mod:`tests.mcs_oracle.lo_recalc`), shelled out to the system Python that
  owns the ``uno`` bridge. The **gold reference**: used by
  :mod:`tests.mcs_oracle.test_certify` to prove the formulas engine stays
  byte-faithful.

Both engines agree on 100% of the 7288 numeric formula cells in the workbook;
see tests/fixtures/mcs/PROVENANCE.md.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import warnings
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_WORKER = _HERE / "lo_recalc.py"

DEFAULT_FIXTURE = (
    _HERE.parent / "fixtures" / "mcs" / "MCS-Heat-Pump-Calculator-original-v2.xlsm"
)

# Debian/LibreOffice ship the uno bridge for the system interpreter only.
SYSTEM_PYTHON = os.environ.get("MCS_ORACLE_SYSTEM_PYTHON", "/usr/bin/python3")
_UNO_PYTHONPATH = "/usr/lib/python3/dist-packages"


# --- LibreOffice (gold reference) ------------------------------------------

def lo_recalc(file: str, inputs: dict, outputs: list[str]) -> dict:
    """Recalculate ``file`` via headless LibreOffice and return ``outputs``."""
    request = {"file": str(file), "inputs": inputs, "outputs": list(outputs)}
    env = dict(os.environ)
    env["PYTHONPATH"] = _UNO_PYTHONPATH + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [SYSTEM_PYTHON, str(_WORKER)],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"LibreOffice worker failed (rc={proc.returncode}):\n{proc.stderr[-2000:]}"
        )
    return json.loads(proc.stdout)["values"]


# --- formulas (fast, default) ----------------------------------------------

_MODEL_CACHE: dict[str, object] = {}


def _load_model(file: str):
    """Compile (and cache) the workbook's formula graph, LOOKUP fix applied."""
    model = _MODEL_CACHE.get(file)
    if model is None:
        from tests.mcs_oracle import formulas_patch

        formulas_patch.apply()  # must precede compilation
        import formulas

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # dangling external refs in the fixture
            model = formulas.ExcelModel().loads(str(file)).finish()
        _MODEL_CACHE[file] = model
    return model


def _fkey(book: str, ref: str) -> str:
    """'Design Details!B19' -> "'[book.xlsm]DESIGN DETAILS'!B19" (formulas key)."""
    sheet, _, a1 = ref.rpartition("!")
    return f"'[{book}]{sheet.upper()}'!{a1}"


def _scalar(value):
    """Unwrap formulas' numpy/Ranges return to a plain scalar (None on error)."""
    try:
        value = value[0, 0]
    except (TypeError, IndexError):
        pass
    if isinstance(value, str):
        return None if value.startswith("#") else value  # '#N/A', '#VALUE!', ...
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def formulas_recalc(file: str, inputs: dict, outputs: list[str]) -> dict:
    """Recalculate ``file`` via the patched ``formulas`` engine."""
    model = _load_model(file)
    book = Path(file).name
    sol = model.calculate(
        inputs={_fkey(book, ref): val for ref, val in inputs.items()} or None
    )
    out = {}
    for ref in outputs:
        key = _fkey(book, ref)
        out[ref] = _scalar(sol[key].value) if key in sol else None
    return out


# Default everyday oracle.
recalc = formulas_recalc


if __name__ == "__main__":  # manual probe: python -m ...recalc <ref> [<ref> ...]
    refs = sys.argv[1:] or ["1!N6"]
    f = str(DEFAULT_FIXTURE)
    print("formulas:   ", formulas_recalc(f, {}, refs))
    print("LibreOffice:", lo_recalc(f, {}, refs))
