"""Test oracle for the MCS Heat Pump Calculator spreadsheet.

The MCS Excel tool (BS EN 12831 room-by-room heat loss) is the authoritative
reference for Phase 1. We drive it headlessly, recalculate, and read cell
values so a Python reimplementation can be diffed against it.

Two interchangeable recalc engines behind one ``set inputs -> read outputs``
interface (see :mod:`tests.mcs_oracle.recalc`):

* **LibreOffice + UNO** (:mod:`tests.mcs_oracle.lo_recalc`) -- the gold
  reference. Runs under the *system* Python (the ``uno`` bridge is ABI-tied to
  LibreOffice's Python 3.11, not this project's 3.12 venv), so it is invoked as
  a subprocess.
* **formulas** -- a pure-Python Excel formula engine, fast and dependency-light,
  used as the everyday CI oracle *once certified* against LibreOffice.

The .xlsm fixture is copyright MCS and not committed; see
``tests/fixtures/mcs/PROVENANCE.md``.
"""
