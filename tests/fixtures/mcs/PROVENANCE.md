# MCS Heat Pump Calculator — test oracle fixture

- File: MCS-Heat-Pump-Calculator-original-v2.xlsm
- sha256: e17ee2f85f4b948928a253fca1d4ab03e158e1077c32b2881c9b915104efcecd
- Source (mirror): https://renewableheatinghub.co.uk/wp-content/uploads/wpforo/attachments/26/948-MCS-Heat-Pump-Calculator-original-v2.xlsm
- Official tool was withdrawn from the MCS Standards & Tools Library on 2026-04-01
  (superseded by the online Heat Load Calculator); archived copy may still be
  obtainable from MCS for certified installers.
- Copyright MCS. NOT committed to git — local fixture only. See .gitignore.
- Structure: 49 sheets, formula-driven (~4250 formula cells). Room sheets named
  "1".."30"; global inputs on "Design Details"; lookups on "Design Tables" /
  "Post Code Degree Days"; ground-floor U-value on "Solid"/"Suspended".
  vbaProject.bin present (~103 KB) but core heat-loss math is plain formulas.

## Recalc engine certification (2026-06-12)

Goal: drive this sheet headlessly as a golden reference for the Phase 1
heat-loss reimplementation. We settled on a **hybrid** of two engines:

- **LibreOffice 7.4 + UNO** -- the gold reference. Reproduces the workbook's own
  cached values to the digit (e.g. room "1" total N6 = 2058.8265376).
- **`formulas` (pure-Python Excel engine)** -- the everyday oracle, *with one
  vendored fix*. Out of the box it agreed with LibreOffice on only ~61% of
  formula cells, because its `LOOKUP` flattens a 2-column search range with
  `np.ravel` instead of applying Excel's array-form rule (search the first
  column / row). That single bug fans out across the sheet (postcode -> design
  temp, element -> U-value). With the ~12-line fix in
  `tests/mcs_oracle/formulas_patch.py`, it matches LibreOffice on **100% of the
  7288 numeric formula cells** across all 49 sheets.

The LOOKUP bug is unreported upstream (closest: vinci1it2000/formulas#170,
HLOOKUP approximate-match). The fix is vendored, not upstreamed (yet); we pin
`formulas==1.3.4` so the monkeypatch can't drift, and
`tests/mcs_oracle/test_certify.py` re-runs the full LibreOffice diff to guard
the pin.

Harness: tests/mcs_oracle/ -- lo_recalc.py (system-python UNO worker),
recalc.py (both engines behind `recalc(file, inputs, outputs)`; default =
patched formulas), formulas_patch.py (the LOOKUP fix), test_oracle.py (fast
smoke tests), test_certify.py (slow LibreOffice certification).
