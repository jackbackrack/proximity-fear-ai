#!/usr/bin/env python3
"""Submit the badge with the Warp layout, capture it, and write the JLCPCB packet (fin-01).

Modelled on socialbadge-ai rev 2 ``scripts/export_jlcpcb.py``. It must be one process: the
layout is applied while the design is constructed (``ProximityFearBadge.__init__`` replays
``jitx_export.json`` through ``layout_placements``), and the packet has to be written from
that same submitted and captured design. Nothing persists between separate invocations.

One difference from socialbadge: its script passes ``layout="jitx_export.json"`` to
``r.submit``; the installed jitx 4.6.0 ``SyncRuntime.submit`` takes only ``design`` and
``name``, so the design's own hook is the import path here.

Run from the project root, venv active, runtime started, after ``python
scripts/check_layout.py proximity_fear.main.ProximityFearBadge`` exits 0:

    python scripts/export_jlcpcb.py

Exit codes: 0 packet written; 2 not run (no layout file, WARP_LIVE=1, or the export failed).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import jitx
import jitx.plugin

from proximity_fear.main import LAYOUT_FILE, ProximityFearBadge

OUTPUT_DIR = Path("jlcpcb")


def main() -> int:
    if not Path(LAYOUT_FILE).exists():
        print(f"not run: {LAYOUT_FILE} not found in {Path.cwd()} (export the Warp layout first)")
        return 2
    if os.environ.get("WARP_LIVE") == "1":
        print("not run: WARP_LIVE=1 skips the layout import, so the packet would be unrouted")
        return 2
    jitx.plugin.initialize()
    exporter = jitx.plugin.Export.get("jlcpcb")
    if exporter is None:
        print("not run: the jlcpcb export plugin is not installed (jitxlib-jlcpcb)")
        return 2
    exporter.preflight(output=OUTPUT_DIR, overwrite=True)
    with jitx.runtime as r:
        rd = r.submit(ProximityFearBadge)
        exporter.submitted(rd, output=OUTPUT_DIR, overwrite=True)
        rd.capture()
        exporter.export(rd, output=OUTPUT_DIR, overwrite=True)
    print(f"wrote {OUTPUT_DIR.absolute()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
