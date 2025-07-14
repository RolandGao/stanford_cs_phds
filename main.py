import pandas as pd
import re

##############################################################################
# 1.  READ THE MARKDOWN TABLE -----------------------------------------------
##############################################################################
raw = pd.read_clipboard(sep=r"\|", engine="python", header=None)
raw = raw.dropna(axis=1, how="all")  # strip blank edges

header_idx = raw.index[
    ~raw.apply(lambda r: r.astype(str).str.fullmatch(r"-+\s*").all(), axis=1)
][0]

df = (
    raw.iloc[header_idx + 1 :]
    .rename(columns=raw.iloc[header_idx])
    .reset_index(drop=True)
)

df.columns = df.columns.str.strip()
df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

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


def canonical(inst):
    """Return a cleaned-up institution name or <NA>."""
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

    # trim trailing “, Country / City / Campus” except UC & U-Maryland
    if not inst.startswith(("University of California,", "University of Maryland,")):
        inst = re.sub(r",\s*[A-Z][A-Za-z.\s]+$", "", inst).strip()

    return inst or pd.NA


df["Inst_canon"] = df["Undergraduate Institution"].apply(canonical)
df = df.dropna(subset=["Inst_canon"])  # drop rows that became NA

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
