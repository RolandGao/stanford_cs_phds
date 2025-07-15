#!/usr/bin/env python3
"""
Count how many students in a “Name | Institution” list come from each
undergraduate institution.

The script expects the *clipboard* to contain lines such as::

    Jing Yu Koh | Singapore University of Technology and Design
    Yiding Jiang | University of California, Berkeley
    …

No header row or markdown separator is required.
"""

import pandas as pd
import re

##############################################################################
# 1.  READ THE “NAME | INSTITUTION” LIST FROM CLIPBOARD ----------------------
##############################################################################
# Split on “|” surrounded by optional whitespace.
# We supply column names explicitly because the list has no header row.
raw = (
    pd.read_clipboard(
        sep=r"\s*\|\s*",
        engine="python",
        header=None,
        names=["Name", "Undergraduate Institution"],
    )
    .dropna(how="all")  # drop completely blank lines if any
    .applymap(lambda x: x.strip() if isinstance(x, str) else x)
)

##############################################################################
# 2.  CANONICALISE SCHOOL NAMES ---------------------------------------------
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
}

MISSING_PAT = re.compile(r"(not\s*(found|available)|^n/?a$)", re.I)


def canonical(inst: str) -> str | pd.NA:
    """Return a cleaned-up institution name or <NA> if missing."""
    if pd.isna(inst):
        return pd.NA
    inst = str(inst).strip()

    # placeholders or dashed rows → NA
    if not inst or re.fullmatch(r"-+", inst) or MISSING_PAT.search(inst):
        return pd.NA

    # expand common abbreviations
    for pat, repl in ALIASES.items():
        if re.search(pat, inst, flags=re.I):
            inst = re.sub(pat, repl, inst, flags=re.I)
            break

    # keep only the first institution in “X & Y”
    inst = inst.split("&")[0].strip()

    # remove balanced (…) and dangling “( …”
    inst = re.sub(r"\([^)]*\)", " ", inst)  # balanced
    inst = re.sub(r"\s*\(.*$", "", inst)  # unmatched
    inst = re.sub(r"\s+", " ", inst).strip()

    # trim trailing “, Country / City / Campus” except UC & U‑Maryland
    if not inst.startswith(("University of California,", "University of Maryland,")):
        inst = re.sub(r",\s*[A-Z][A-Za-z.\s]+$", "", inst).strip()

    return inst or pd.NA


raw["Inst_canon"] = raw["Undergraduate Institution"].apply(canonical)

df = raw.dropna(subset=["Inst_canon"])  # drop rows that became NA

##############################################################################
# 3.  AGGREGATE COUNTS -------------------------------------------------------
##############################################################################
school_counts = (
    df.groupby("Inst_canon", as_index=False)
    .size()
    .rename(columns={"size": "Student Count"})
    .sort_values("Student Count", ascending=False)
    .reset_index(drop=True)
)

##############################################################################
# 4.  DISPLAY RESULT ---------------------------------------------------------
##############################################################################
print(school_counts.to_string(index=False))

# Optional: persist to disk
# school_counts.to_csv("school_counts_final.csv", index=False)
