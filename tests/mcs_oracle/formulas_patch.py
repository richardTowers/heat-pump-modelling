"""Vendored fix for a ``LOOKUP`` bug in ``formulas`` 1.3.4.

``formulas``' ``LOOKUP`` flattens a 2-D search range with ``np.ravel`` instead
of applying Excel's array-form orientation rule. For a 2-column range like the
MCS sheet's ``'Post Code Degree Days'!A3:B126`` this interleaves the two
columns, so the search runs over ``[A3, B3, A4, B4, ...]`` and returns the wrong
cell -- or ``#VALUE!`` for the 3-argument form. That one bug fans out across the
whole workbook (postcode -> design temp, element -> U-value), dropping the
pure-Python engine to ~61% agreement with LibreOffice.

With this shim applied, ``formulas`` matches LibreOffice on 100% of the 7288
numeric formula cells in the MCS workbook. We pin ``formulas==1.3.4`` so the
monkeypatched internals can't shift underneath us, and the LibreOffice
certification test (:mod:`tests.mcs_oracle.test_certify`) guards against
regressions if that pin is ever bumped.

Excel ``LOOKUP`` array-form semantics implemented here:
* a range taller than (or as tall as) it is wide -> search its first column,
  return from the last column;
* a range wider than tall -> search its first row, return from the last row;
* the 3-argument form -> reduce the search range to that single first
  row/column, and use the explicit result vector.

Not upstreamed (yet): see tests/fixtures/mcs/PROVENANCE.md.
"""

from __future__ import annotations

import numpy as np

_applied = False


def _fixed_args_parser_lookup_array(lookup_val, lookup_vec, result_vec=None, match_type=1):
    import formulas.functions.look as look

    arr = np.atleast_2d(lookup_vec)
    n_rows, n_cols = arr.shape
    if result_vec is None:  # 2-arg "array" form: search first, return last
        if n_cols > n_rows:
            search, result = arr[0], arr[-1]
        else:
            search, result = arr[:, 0], arr[:, -1]
    else:  # 3-arg form: reduce search to its long axis; explicit result vector
        search = arr[0] if n_cols > n_rows else arr[:, 0]
        result = np.ravel(result_vec)
    return look.args_parser_match_array(lookup_val, np.ravel(search), match_type) + (
        np.ravel(result),
    )


def apply() -> None:
    """Idempotently install the LOOKUP fix. Call before compiling a model."""
    global _applied
    if _applied:
        return
    import formulas

    if formulas.__version__ != "1.3.4":  # pragma: no cover - guarded by the pin
        raise RuntimeError(
            f"formulas_patch targets formulas==1.3.4, found {formulas.__version__}; "
            "re-verify the LOOKUP fix and the certification test before bumping."
        )

    import formulas.functions.look as look
    from formulas.functions import get_error, wrap_ufunc

    look.FUNCTIONS["LOOKUP"] = wrap_ufunc(
        look.xlookup,
        input_parser=lambda *a: a,
        args_parser=_fixed_args_parser_lookup_array,
        check_error=lambda *a: get_error(a[1]),
        excluded={3, 4, 5, 6, 7, 8},
    )
    _applied = True
