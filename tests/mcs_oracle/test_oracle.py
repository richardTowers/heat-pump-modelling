"""Smoke tests for the MCS spreadsheet oracle (default engine).

These exercise the everyday oracle -- the patched ``formulas`` engine -- so they
run in CI without LibreOffice. They prove we can drive the MCS Heat Pump
Calculator: read recalculated cells, and have an input change propagate
correctly. The foundation for the Phase 2 comparison tests, which will feed our
house model into the sheet and diff its room outputs against
``heat_pump_modelling.heat_loss``.

The LibreOffice gold reference and the byte-for-byte certification of this
engine live in :mod:`tests.mcs_oracle.test_certify`.

Skipped when the (uncommitted, copyright-MCS) fixture is absent, so fresh clones
stay green. See tests/fixtures/mcs/PROVENANCE.md.
"""

import pytest

from tests.mcs_oracle.recalc import DEFAULT_FIXTURE, recalc

pytestmark = pytest.mark.skipif(
    not DEFAULT_FIXTURE.exists(),
    reason=f"MCS fixture not present: {DEFAULT_FIXTURE.name} (copyright MCS, not committed)",
)

F = str(DEFAULT_FIXTURE)

# The MCS sheet's worked example (room "1"); both engines reproduce these.
ROOM1_BASELINE = {
    "1!C4": 21.0,  # internal design temp
    "1!C5": -4.3,  # external design temp (postcode KA -> lookup)
    "1!C6": 25.3,  # design delta-T = C4 - C5
    "1!N6": 2058.8265376,  # room total heat loss [W]
}


def _close(a, b, rel=1e-4, abs_=1e-6):
    return abs(a - b) <= abs_ + rel * (abs(a) + abs(b)) / 2


def test_recalc_reproduces_worked_example():
    got = recalc(F, {}, list(ROOM1_BASELINE))
    for ref, expected in ROOM1_BASELINE.items():
        assert got[ref] is not None, f"{ref} evaluated to an error"
        assert _close(got[ref], expected), f"{ref}: got {got[ref]}, expected {expected}"


def test_input_change_propagates():
    """Overriding the external design temperature must flow through to the
    design delta-T and raise the room load; the ground-floor portion, which
    loses heat to ground (not air), keeps it below the pure delta-T ratio."""
    base = recalc(F, {}, ["1!C6", "1!N6"])
    cold = recalc(F, {"Design Details!B19": -10.0}, ["1!C5", "1!C6", "1!N6"])

    assert _close(cold["1!C5"], -10.0)
    assert _close(cold["1!C6"], 31.0)  # 21 - (-10)
    assert cold["1!N6"] > base["1!N6"]  # colder outside -> more loss

    air_dt_ratio = 31.0 / base["1!C6"]
    load_ratio = cold["1!N6"] / base["1!N6"]
    assert 1.0 < load_ratio < air_dt_ratio
