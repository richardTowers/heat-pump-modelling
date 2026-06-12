"""Certify the patched ``formulas`` engine against LibreOffice.

LibreOffice (via UNO) reproduces the MCS workbook's own cached values to the
digit, so it is our gold reference. This test recalculates every numeric
formula cell in both engines and asserts they agree, proving the vendored
LOOKUP fix (:mod:`tests.mcs_oracle.formulas_patch`) keeps the fast engine
byte-faithful. If the ``formulas`` pin is ever bumped and the monkeypatch
silently breaks, this fails.

Heavy and infrastructure-dependent (boots LibreOffice, compiles the whole
formula graph), so it is skipped when LibreOffice or the fixture is absent and
marked ``slow``. Run explicitly with ``-m slow`` or ``-k certify``.
"""

import os
import shutil

import pytest

from tests.mcs_oracle.recalc import DEFAULT_FIXTURE, formulas_recalc, lo_recalc

openpyxl = pytest.importorskip("openpyxl")

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        shutil.which("soffice") is None, reason="LibreOffice (soffice) not installed"
    ),
    pytest.mark.skipif(
        not DEFAULT_FIXTURE.exists(),
        reason=f"MCS fixture not present: {DEFAULT_FIXTURE.name} (copyright MCS)",
    ),
    pytest.mark.skipif(
        not os.path.exists("/usr/bin/python3"), reason="system python (uno bridge) absent"
    ),
]

F = str(DEFAULT_FIXTURE)


def _numeric_formula_cells():
    """Every cell that is a formula with a numeric cached value, any sheet."""
    wbf = openpyxl.load_workbook(F, data_only=False, read_only=True)
    wbv = openpyxl.load_workbook(F, data_only=True, read_only=True)
    refs = []
    for sheet in wbf.sheetnames:
        for row_f, row_v in zip(wbf[sheet].iter_rows(), wbv[sheet].iter_rows()):
            for cell_f, cell_v in zip(row_f, row_v):
                is_formula = isinstance(cell_f.value, str) and cell_f.value.startswith("=")
                is_number = isinstance(cell_v.value, (int, float)) and not isinstance(
                    cell_v.value, bool
                )
                if is_formula and is_number:
                    refs.append(f"{sheet}!{cell_f.coordinate}")
    return refs


def _close(a, b, rel=1e-4, abs_=1e-6):
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= abs_ + rel * abs(a)


def test_formulas_matches_libreoffice_everywhere():
    refs = _numeric_formula_cells()
    assert len(refs) > 5000, f"expected the full workbook, only found {len(refs)} cells"

    gold = lo_recalc(F, {}, refs)
    fast = formulas_recalc(F, {}, refs)

    mismatches = [
        (ref, gold.get(ref), fast.get(ref))
        for ref in refs
        if not _close(gold.get(ref), fast.get(ref))
    ]
    assert not mismatches, (
        f"{len(mismatches)}/{len(refs)} cells diverge; first few: {mismatches[:10]}"
    )
