#!/usr/bin/env python3
"""AuraPOS rebrand — mechanical call-site migration.

Fixes the root patterns across every template, NORMALIZING CRLF -> LF first
(templates shipped with Windows CRLF endings, which broke naive replacements):
  1. The 3-stop neon brand gradient (literal class copies) -> .btn-brand / .brand-gradient
  2. Cold blue-black surfaces + neon hexes                     -> warm-ink / ember equivalents
  3. Neon rgba() literals                                      -> ember / gold equivalents

Idempotent: running again must be a no-op because replacements no longer match.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(r"c:\Users\Aayush\Desktop\python_projects_shared\salon-software")
TEMPLATES = ROOT / "templates"

GRADIENTS = [
    ("bg-gradient-to-r from-neon-magenta via-neon-violet to-neon-cyan", "btn-brand"),
    ("bg-gradient-to-r from-neon-magenta via-violet-600 to-neon-cyan", "btn-brand"),
    ("bg-gradient-to-t from-violet-600 via-neon-magenta to-neon-cyan", "brand-gradient"),
    ("bg-gradient-to-tr from-neon-magenta to-violet-600", "brand-gradient"),
    ("bg-gradient-to-br from-neon-magenta to-violet-600", "brand-gradient"),
    ("bg-gradient-to-tr from-neon-magenta to-neon-cyan", "brand-gradient"),
    ("bg-gradient-to-r from-neon-magenta to-violet-600", "btn-brand"),
    ("bg-gradient-to-r from-violet-600 to-neon-cyan", "btn-brand"),
    ("bg-gradient-to-r from-neon-magenta to-amber-500", "btn-brand"),
    ("bg-gradient-to-r from-amber-500 to-neon-magenta", "btn-brand"),
]
# JS palettes in staff.html/reports.html store them without the `bg-…` prefix.
JS_PALETTES = [
    ("'from-neon-magenta via-violet-600 to-neon-cyan',", "'btn-brand',"),
    ("'from-violet-600 to-neon-cyan',", "'btn-brand',"),
    ("'from-neon-cyan to-emerald-500',", "'bg-gradient-to-r from-amber-400 to-orange-600',"),
    ("'from-amber-500 to-neon-magenta',", "'bg-gradient-to-r from-amber-400 to-orange-600',"),
    ("\"from-neon-magenta via-violet-600 to-neon-cyan\",", "\"btn-brand\","),
    ("\"from-violet-600 to-neon-cyan\",", "\"btn-brand\","),
    ("\"from-neon-cyan to-emerald-500\",", "\"bg-gradient-to-r from-amber-400 to-orange-600\","),
    ("\"from-amber-500 to-neon-magenta\",", "\"bg-gradient-to-r from-amber-400 to-orange-600\","),
]
HEXES = [
    ("#050508", "#0d0c0a"),
    ("#08080c", "#0a0908"),
    ("#09090e", "#100e0c"),
    ("#0c0c12", "#141210"),
    ("#0f0f15", "#181512"),
    ("#0f0f16", "#181512"),
    ("#111118", "#1b1815"),
    ("#141420", "#1b1815"),
    ("#0d0d16", "#141210"),
    ("#12081f", "#1c1410"),
    ("#1c0b2e", "#241a12"),
    ("#0a1412", "#141210"),
    ("#f7f7f2", "#faf9f7"),
    ("#f3f4f6", "#f4f2ed"),
    ("#00f5d4", "#fbbf24"),
    ("#f72585", "#fb923c"),
    ("#7b2cbf", "#c2410c"),
]
RGBAS = [
    ("rgba(0,245,212,", "rgba(251,191,36,"),
    ("rgba(0, 245, 212,", "rgba(251, 191, 36,"),
    ("rgba(247,37,133,", "rgba(251,146,60,"),
    ("rgba(247, 37, 133,", "rgba(251, 146, 60,"),
    ("rgba(123,44,191,", "rgba(194,65,12,"),
    ("rgba(123, 44, 191,", "rgba(194, 65, 12,"),
]


def main() -> int:
    files = sorted(TEMPLATES.rglob("*.html"))
    totals = {"gradient": 0, "js": 0, "hex": 0, "rgba": 0, "eol": 0}
    changed = 0
    for path in files:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        hits = {"gradient": 0, "js": 0, "hex": 0, "rgba": 0, "eol": 0}
        if "\r\n" in text:
            hits["eol"] = text.count("\r\n")
            text = text.replace("\r\n", "\n")
        for old, new in GRADIENTS:
            n = text.count(old)
            if n:
                text = text.replace(old, new)
                hits["gradient"] += n
        for old, new in JS_PALETTES:
            n = text.count(old)
            if n:
                text = text.replace(old, new)
                hits["js"] += n
        for old, new in HEXES:
            n = text.count(old)
            if n:
                text = text.replace(old, new)
                hits["hex"] += n
        for old, new in RGBAS:
            n = text.count(old)
            if n:
                text = text.replace(old, new)
                hits["rgba"] += n
        if text != raw.decode("utf-8"):
            path.write_bytes(text.encode("utf-8"))
            changed += 1
            for k in totals:
                totals[k] += hits[k]
            print(f"  {str(path.relative_to(ROOT)):<44} " + " ".join(f"{k}={hits[k]}" for k in hits))
    print()
    print(f"files changed : {changed} / {len(files)}")
    print(f"gradients     : {totals['gradient']}")
    print(f"js palettes   : {totals['js']}")
    print(f"hex swaps     : {totals['hex']}")
    print(f"rgba swaps    : {totals['rgba']}")
    print(f"crlf fixed    : {totals['eol']}")
    print(f"total edits   : {sum(totals.values()) - totals['eol']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

