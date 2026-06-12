#!/usr/bin/env python3
"""Headless LibreOffice recalc worker (gold reference).

Runs under the **system** Python 3.11 that owns the ``uno`` bridge, NOT the
project venv. Invoked as a subprocess by :mod:`tests.mcs_oracle.recalc`.

Protocol: a single JSON request on stdin, a single JSON response on stdout::

    request  = {"file": "<path>",
                "inputs":  {"<Sheet>!<A1>": <number|string>, ...},
                "outputs": ["<Sheet>!<A1>", ...]}
    response = {"values": {"<Sheet>!<A1>": <number|string|null>, ...}}

The worker boots its own private headless ``soffice`` instance (unique socket
+ throwaway user profile), loads the workbook hidden, writes the input cells,
forces a full recalculation, reads the output cells, then tears the instance
down. ``null`` is returned for a cell that evaluates to an error.

Why a fresh soffice per call: it keeps the worker self-contained and stateless,
which matters more than latency for a test oracle (a handful of calls per run).
"""

import json
import os
import subprocess
import sys
import tempfile
import time

SOFFICE = "/usr/bin/soffice"


def _split_ref(ref):
    """'Design Details!B19' -> ('Design Details', 'B19'). Sheet names may
    contain '!'? They cannot in Excel, so split on the last '!'."""
    sheet, _, a1 = ref.rpartition("!")
    if not sheet:
        raise ValueError(f"bad cell ref (expected Sheet!A1): {ref!r}")
    return sheet, a1


def _boot_soffice(port, profile_dir):
    """Launch a private headless soffice listening on a UNO socket."""
    args = [
        SOFFICE,
        "--headless",
        "--invisible",
        "--norestore",
        "--nologo",
        "--nodefault",
        "--nofirststartwizard",
        f"--accept=socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext",
        f"-env:UserInstallation=file://{profile_dir}",
    ]
    # Own session/process group so we can reliably kill it and its children.
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _connect(port, timeout_s=60):
    """Resolve a UNO connection to the soffice socket, retrying until it's up."""
    import uno
    from com.sun.star.connection import NoConnectException

    local_ctx = uno.getComponentContext()
    resolver = local_ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local_ctx
    )
    url = f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext"
    deadline = time.monotonic() + timeout_s
    last_exc = None
    while time.monotonic() < deadline:
        try:
            ctx = resolver.resolve(url)
            smgr = ctx.ServiceManager
            desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
            return desktop
        except NoConnectException as exc:  # soffice not listening yet
            last_exc = exc
            time.sleep(0.25)
    raise TimeoutError(f"could not connect to soffice on port {port}: {last_exc}")


def _load_hidden(desktop, path):
    import uno  # noqa: F401
    from com.sun.star.beans import PropertyValue

    hidden = PropertyValue()
    hidden.Name = "Hidden"
    hidden.Value = True
    url = "file://" + os.path.abspath(path)
    return desktop.loadComponentFromURL(url, "_blank", 0, (hidden,))


def _read_cell(sheet, a1):
    """Return float for a value/numeric-formula cell, str for text, or None on
    a formula error."""
    cell = sheet.getCellRangeByName(a1)
    # com.sun.star.table.CellContentType: EMPTY=0 VALUE=1 TEXT=2 FORMULA=3
    ctype = cell.getType().value
    if ctype == "FORMULA":
        if cell.getError() != 0:
            return None
        # numeric vs string formula result
        if cell.FormulaResultType.value == "STRING":
            return cell.getString()
        return cell.getValue()
    if ctype == "TEXT":
        return cell.getString()
    if ctype == "VALUE":
        return cell.getValue()
    return None  # EMPTY


def run(request):
    path = request["file"]
    inputs = request.get("inputs", {})
    outputs = request.get("outputs", [])

    port = 2002 + (os.getpid() % 4000)
    profile_dir = tempfile.mkdtemp(prefix="lo_profile_")
    proc = _boot_soffice(port, profile_dir)
    doc = None
    try:
        desktop = _connect(port)
        doc = _load_hidden(desktop, path)
        sheets = doc.Sheets

        for ref, value in inputs.items():
            sheet_name, a1 = _split_ref(ref)
            cell = sheets.getByName(sheet_name).getCellRangeByName(a1)
            if isinstance(value, bool):
                cell.setValue(1.0 if value else 0.0)
            elif isinstance(value, (int, float)):
                cell.setValue(float(value))
            elif value is None:
                cell.setString("")
            else:
                cell.setString(str(value))

        doc.calculateAll()

        values = {}
        for ref in outputs:
            sheet_name, a1 = _split_ref(ref)
            values[ref] = _read_cell(sheets.getByName(sheet_name), a1)
        return {"values": values}
    finally:
        try:
            if doc is not None:
                doc.close(False)
        except Exception:
            pass
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()


def main():
    request = json.load(sys.stdin)
    json.dump(run(request), sys.stdout)
    sys.stdout.flush()


if __name__ == "__main__":
    main()
