#!/usr/bin/env python3
"""
MIT-only list → counts of undergraduate institutions (no department breakdown).

Usage
-----
1. Copy the student list, one entry per line:

       <Name> | <Undergraduate Institution>

2. Run this script; it prints a single table like

       === MIT OVERALL ===
       Undergraduate Institution               Student Count
       Tsinghua University                                7
       ⋮

The script keeps campus-specific IIT names separate (e.g. *Indian Institute of
Technology, Delhi* vs *IIT Kanpur*), merges common spelling variants for a few
schools, and collapses obvious abbreviations.
"""

from __future__ import annotations

import re
import sys
from typing import List

import pandas as pd

# ──────────────────────────────────────────────────────────────────────
# 1. READ RAW TEXT FROM THE CLIPBOARD
# ──────────────────────────────────────────────────────────────────────
try:
    # pandas ≥ 1.5
    from pandas.io.clipboard import clipboard_get  # type: ignore
except ImportError:  # pragma: no cover – older pandas fallback
    from pandas.io import clipboard as _clipboard  # type: ignore

    clipboard_get = _clipboard.clipboard_get  # type: ignore

try:
    clipboard_text: str = clipboard_get()
except Exception as exc:  # pragma: no cover
    sys.exit(f"❌ Could not read clipboard: {exc}")

raw_lines = [ln.rstrip("\r") for ln in clipboard_text.splitlines() if ln.strip()]
if not raw_lines:
    sys.exit("❌ Clipboard appears to be empty.")

# ──────────────────────────────────────────────────────────────────────
# 2. PARSE LINES → STUDENT RECORDS (no departments)
# ──────────────────────────────────────────────────────────────────────
records: List[dict[str, str]] = []
for line in raw_lines:
    if "|" not in line:
        continue  # ignore non-data lines

    name, inst = (seg.strip() for seg in line.split("|", 1))
    if not name or not inst:
        continue  # malformed entry

    records.append({"Name": name, "Undergraduate Institution": inst})

if not records:
    sys.exit("❌ No valid student rows detected – check the clipboard format.")

# ──────────────────────────────────────────────────────────────────────
# 3. CANONICALISE SCHOOL NAMES
# ──────────────────────────────────────────────────────────────────────
ALIASES = {
    # — common US shortcuts —
    r"\bMIT\b": "Massachusetts Institute of Technology",
    r"\bCaltech\b": "California Institute of Technology",
    r"\bCMU\b": "Carnegie Mellon University",
    r"\bGeorgia\s*Tech\b": "Georgia Institute of Technology",
    r"\bUW\b": "University of Washington",
    # — UC campuses —
    r"\bUC\s*Berkeley\b|\bUCB\b": "University of California, Berkeley",
    r"\bUCSD\b": "University of California, San Diego",
    r"\bUCLA\b": "University of California, Los Angeles",
    r"\bUC\s*Davis\b": "University of California, Davis",
    r"\bUCI\b": "University of California, Irvine",
    r"\bUCSB\b": "University of California, Santa Barbara",
    # — Asia / Europe shortcuts —
    r"\bSJTU\b": "Shanghai Jiao Tong University",
    r"\bUSTC\b": "University of Science and Technology of China",
    r"\bBITS?\s*Pilani\b": "Birla Institute of Technology and Science",
    r"\bPOSTECH\b": "Pohang University of Science and Technology",
    r"\bEPFL\b": "École Polytechnique Fédérale de Lausanne",
    # — NEW: merge variants / duplicates —
    r"\bUniversity of Illinois\s*(at\s*)?Urbana[- ]?Champaign\b": "University of Illinois Urbana-Champaign",
    r"\bHarvard College\b": "Harvard University",
}

MISSING_PAT = re.compile(r"(not\s*(found|available)|^n/?a$)", re.I)


def canonical(inst: str | pd.NA) -> str | pd.NA:
    """Return a cleaned-up school name, or <NA> if missing."""
    if pd.isna(inst):
        return pd.NA

    inst = str(inst).strip()
    if not inst or re.fullmatch(r"-+", inst) or MISSING_PAT.search(inst):
        return pd.NA

    # keep only the first institution if multiple separated by ';' or '&'
    inst = re.split(r"[;&]", inst)[0].strip()

    # apply alias expansions
    for pat, repl in ALIASES.items():
        if re.search(pat, inst, flags=re.I):
            inst = re.sub(pat, repl, inst, flags=re.I)
            break

    # strip parenthetical notes
    inst = re.sub(r"\([^)]*\)", " ", inst)  # balanced (…)
    inst = re.sub(r"\s*\(.*$", "", inst)  # unmatched opening '('
    inst = re.sub(r"\s+", " ", inst).strip()  # collapse whitespace

    # ── SPECIAL RULE: preserve IIT campus suffixes ──────────────────
    if inst.startswith("Indian Institute of Technology"):
        return inst

    # strip trailing “, City/Country” (except UC & U-Maryland prefixes)
    if not inst.startswith(("University of California,", "University of Maryland,")):
        inst = re.sub(r",\s*[A-Z][A-Za-z.\s]+$", "", inst).strip()

    return inst or pd.NA


df = pd.DataFrame.from_records(records)
df["Inst_canon"] = df["Undergraduate Institution"].apply(canonical)
df = df.dropna(subset=["Inst_canon"]).reset_index(drop=True)

# ──────────────────────────────────────────────────────────────────────
# 4. AGGREGATE & DISPLAY
# ──────────────────────────────────────────────────────────────────────
overall = (
    df.groupby("Inst_canon", as_index=False)
    .size()
    .rename(columns={"size": "Student Count"})
    .sort_values("Student Count", ascending=False)
)

print("\n=== MIT OVERALL ===")
print(overall.to_string(index=False))

# Optional: persist to CSV
# overall.to_csv("mit_overall_counts.csv", index=False)
