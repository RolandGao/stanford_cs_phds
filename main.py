import pandas as pd
import re

##############################################################################
# 1.  READ THE RAW MARKDOWN TABLE (clipboard or file) ------------------------
##############################################################################
raw = pd.read_clipboard(sep=r"\|", engine="python", header=None)
raw = raw.dropna(axis=1, how="all")  # drop the blank edges

# promote the real header row
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
# 2.  NORMALISE / CANONICALISE SCHOOL NAMES ----------------------------------
##############################################################################
ALIASES = {
    r"\bMIT\b": "Massachusetts Institute of Technology",
    r"\bCaltech\b": "California Institute of Technology",
    r"\bGeorgia\s*Tech\b": "Georgia Institute of Technology",
    r"\bUCSD\b": "University of California, San Diego",
    r"\bUCLA\b": "University of California, Los Angeles",
    r"\bUC\s*Berkeley\b": "University of California, Berkeley",
    r"\bUSC\b": "University of Southern California",
    r"\bEPFL\b": "École Polytechnique Fédérale de Lausanne",
    r"\bBITS?\s*Pilani\b": "Birla Institute of Technology and Science",
    r"\bPOSTECH\b": "Pohang University of Science and Technology",
}


def canonical(inst: str | float):
    """Return a clean, de-duplicated institution name or <NA>."""
    if pd.isna(inst):
        return pd.NA
    inst = str(inst).strip()

    # zap obvious placeholders or dashed rows
    if not inst or re.fullmatch(r"-+", inst) or re.search(r"not\s*found", inst, re.I):
        return pd.NA

    # keep only the first part of “X & Y” composites
    inst = inst.split("&")[0].strip()

    # remove ALL parenthetical segments – wherever they appear
    inst = re.sub(r"\([^)]*\)", "", inst)

    # strip trailing “, Country / City / Campus”
    inst = re.sub(r",\s*[A-Z][A-Za-z.\s]+$", "", inst)

    # collapse multiple spaces left behind
    inst = re.sub(r"\s+", " ", inst).strip()

    # apply nickname / abbreviation aliases
    for pat, repl in ALIASES.items():
        if re.search(pat, inst, flags=re.I):
            inst = repl
            break

    return inst or pd.NA


df["Inst_canon"] = df["Undergraduate Institution"].apply(canonical)

# drop rows that ended up blank or NA
df = df.dropna(subset=["Inst_canon"])

##############################################################################
# 3.  AGGREGATE --------------------------------------------------------------
##############################################################################
school_counts = (
    df.groupby("Inst_canon", as_index=False)
    .size()
    .rename(columns={"size": "Student Count"})
    .sort_values("Student Count", ascending=False)
    .reset_index(drop=True)
)

##############################################################################
# 4.  SEE / SAVE THE RESULT --------------------------------------------------
##############################################################################
print(school_counts.to_string(index=False))  # console view
# school_counts.to_csv("school_counts_clean.csv", index=False)  # optional file
