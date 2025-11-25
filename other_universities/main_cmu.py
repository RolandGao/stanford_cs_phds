#!/usr/bin/env python3
"""
Count how many students in each department (CSD, ML, LTI …) come from each
undergraduate institution, plus an overall total.

Paste the full list (with department headings) into your clipboard and run the
script. It prints:

* One table per department, sorted by descending count.
* A final **ALL DEPARTMENTS** summary.

Improvements in this revision
-----------------------------
* Robust clipboard capture (works on all OSes; no newline–separator error).
* Treat **Unknown / unknown / Unknown institution …** as missing and drop them.
* Normalise en‑ and em‑dashes (“–”, “—”) to hyphens to merge e.g.
  “University of Illinois at Urbana‑Champaign” variants.
* Added regex aliases to merge common variants such as:
  * University of Illinois at Urbana–Champaign ↔ Urbana-Champaign
  * University of Maryland Baltimore County ↔ , Baltimore County
* Department headings can optionally be restricted via `ALLOWED_DEPTS`.
"""

from __future__ import annotations

import re
import sys
from typing import List, Optional

import pandas as pd

##############################################################################
# 0.  OPTIONAL: LIMIT WHICH DEPARTMENT CODES ARE RECOGNISED ------------------
##############################################################################
ALLOWED_DEPTS: Optional[set[str]] = {"CSD", "ML", "LTI"}  # set(None) to allow all
ALLOWED_DEPTS = None

##############################################################################
# 1.  READ RAW TEXT FROM CLIPBOARD ------------------------------------------
##############################################################################
try:
    # pandas ≥ 1.5
    from pandas.io.clipboard import clipboard_get  # type: ignore
except ImportError:  # pragma: no cover
    from pandas.io import clipboard as _clipboard  # type: ignore

    clipboard_get = _clipboard.clipboard_get  # type: ignore

try:
    clipboard_text: str = clipboard_get()
except Exception as exc:  # pragma: no cover
    sys.exit(f"❌ Could not read clipboard: {exc}")

raw_lines = [ln.rstrip("\r") for ln in clipboard_text.splitlines() if ln.strip()]
if not raw_lines:
    sys.exit("❌ Clipboard appears to be empty.")

##############################################################################
# 2.  PARSE LINES INTO STUDENT RECORDS --------------------------------------
##############################################################################
records: List[dict[str, str]] = []
current_dept: str | None = None

for line in raw_lines:
    if "|" not in line:  # potential department heading
        dept_candidate = line.strip()
        if ALLOWED_DEPTS is None or dept_candidate in ALLOWED_DEPTS:
            current_dept = dept_candidate
        # else ignore stray headings (e.g. RI) that aren't of interest
        continue

    if current_dept is None:
        continue  # ignore lines before first recognised department

    name, inst = (seg.strip() for seg in line.split("|", 1))
    if not name or not inst:
        continue  # malformed – skip

    records.append(
        {
            "Name": name,
            "Undergraduate Institution": inst,
            "Dept": current_dept,
        }
    )

if not records:
    sys.exit("❌ No student lines detected – check the clipboard format/dept names.")

##############################################################################
# 3.  CANONICALISE SCHOOL NAMES ---------------------------------------------
##############################################################################
ALIASES = {
    # ── common US shortcuts ─────────────────────────────────────────
    r"\bMIT\b": "Massachusetts Institute of Technology",
    r"\bCaltech\b": "California Institute of Technology",
    r"\bCMU\b": "Carnegie Mellon University",
    r"\bGeorgia\s*Tech\b": "Georgia Institute of Technology",
    r"\bUW\b": "University of Washington",
    # ── UC campuses ────────────────────────────────────────────────
    r"\bUC\s*Berkeley\b|\bUCB\b": "University of California, Berkeley",
    r"\bUCSD\b": "University of California, San Diego",
    r"\bUCLA\b": "University of California, Los Angeles",
    r"\bUC\s*Davis\b": "University of California, Davis",
    r"\bUCI\b": "University of California, Irvine",
    r"\bUCSB\b": "University of California, Santa Barbara",
    # ── Asia / Europe shortcuts ────────────────────────────────────
    r"\bSJTU\b": "Shanghai Jiao Tong University",
    r"\bUSTC\b": "University of Science and Technology of China",
    r"\bBITS?\s*Pilani\b": "Birla Institute of Technology and Science",
    r"\bPOSTECH\b": "Pohang University of Science and Technology",
    r"\bEPFL\b": "École Polytechnique Fédérale de Lausanne",
    # ── dash‑variant aliases ───────────────────────────────────────
    r"University of Illinois at Urbana[–-]Champaign": "University of Illinois at Urbana-Champaign",
    r"University of Maryland(?:,)? Baltimore County": "University of Maryland, Baltimore County",
}

MISSING_PAT = re.compile(
    r"^(unknown|undergrad institution not found|institution not confirmed|not\s*(found|available)|n/?a)$",
    re.I,
)


def canonical(inst: str | pd.NA) -> str | pd.NA:
    """Return a cleaned‑up institution name or <NA> if missing/unknown."""
    if pd.isna(inst):
        return pd.NA

    inst = str(inst).strip()
    # normalise Unicode dashes to ASCII hyphen
    inst = inst.replace("–", "-").replace("—", "-")

    # placeholders or dashed rows → NA
    if not inst or re.fullmatch(r"-+", inst) or MISSING_PAT.fullmatch(inst):
        return pd.NA

    # keep only the first institution if multiple are separated by ';' or '&'
    inst = re.split(r"[;&]", inst)[0].strip()

    # expand common abbreviations / aliases
    for pat, repl in ALIASES.items():
        if re.search(pat, inst, flags=re.I):
            inst = re.sub(pat, repl, inst, flags=re.I)
            break

    # remove balanced (…) and dangling “( …”
    inst = re.sub(r"\([^)]*\)", " ", inst)  # balanced parentheses
    inst = re.sub(r"\s*\(.*$", "", inst)  # unmatched opening “(”
    inst = re.sub(r"\s+", " ", inst).strip()  # collapse whitespace

    # trim trailing “, Country / City / Campus” except UC & U‑Maryland
    if not inst.startswith(("University of California,", "University of Maryland,")):
        inst = re.sub(r",\s*[A-Z][A-Za-z.\s]+$", "", inst).strip()

    return inst or pd.NA


df = pd.DataFrame.from_records(records)
df["Inst_canon"] = df["Undergraduate Institution"].apply(canonical)

# Drop rows where the institution could not be resolved
initial_rows, final_rows = len(df), df["Inst_canon"].notna().sum()
df = df.dropna(subset=["Inst_canon"]).reset_index(drop=True)

##############################################################################
# 4.  AGGREGATE COUNTS -------------------------------------------------------
##############################################################################
per_dept = (
    df.groupby(["Dept", "Inst_canon"], as_index=False)
    .size()
    .rename(columns={"size": "Student Count"})
    .sort_values(["Dept", "Student Count", "Inst_canon"], ascending=[True, False, True])
)

overall = (
    df.groupby("Inst_canon", as_index=False)
    .size()
    .rename(columns={"size": "Student Count"})
    .sort_values(["Student Count", "Inst_canon"], ascending=[False, True])
)

##############################################################################
# 5.  DISPLAY RESULT ---------------------------------------------------------
##############################################################################
for dept in per_dept["Dept"].unique():
    print(f"\n=== {dept} ===")
    print(
        per_dept[per_dept["Dept"] == dept].drop(columns="Dept").to_string(index=False)
    )

print("\n=== ALL DEPARTMENTS ===")
print(overall.to_string(index=False))

##############################################################################
# 6.  DEBUG SUMMARY (optional) ----------------------------------------------
##############################################################################
print(f"\nProcessed {initial_rows} rows; kept {final_rows} after cleaning.")

# Optional: save CSVs
# per_dept.to_csv("dept_counts.csv", index=False)
# overall.to_csv("overall_counts.csv", index=False)
