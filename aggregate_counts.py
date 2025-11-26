#!/usr/bin/env python3
"""Aggregate counts of undergrad schools from a processed Stanford list.

Reads a file with lines like:

    Name | School

and writes a sorted count table to an output file. Includes light
canonicalisation (alias expansion + cleanup) to collapse spelling variants.
"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, Iterator, List, Tuple


# Expand this alias map as you notice more spellings.
ALIASES: Dict[str, str] = {
    r"\bMIT\b": "Massachusetts Institute of Technology",
    r"\bCaltech\b": "California Institute of Technology",
    r"\bCMU\b": "Carnegie Mellon University",
    r"\bGeorgia\s*Tech\b": "Georgia Institute of Technology",
    r"\bUW\b": "University of Washington",
    r"\bU\.?\s*Chicago\b": "University of Chicago",
    # UC campuses
    r"\bUC\s*Berkeley\b|\bUCB\b": "University of California, Berkeley",
    r"\bUCSD\b|\bUC\s*San\s*Diego\b|^University of California San Diego$": "University of California, San Diego",
    r"\bUCLA\b": "University of California, Los Angeles",
    r"\bUC\s*Davis\b": "University of California, Davis",
    r"\bUCI\b": "University of California, Irvine",
    r"\bUCSB\b": "University of California, Santa Barbara",
    # Other common variants
    r"University of Illinois at Urbana-Champaign": "University of Illinois Urbana-Champaign",
    r"^The University of North Carolina at Chapel Hill$": "University of North Carolina at Chapel Hill",
    r"^The University of Sydney$": "University of Sydney",
    r"^Brown University and Rhode Island School of Design$": "Brown University",
    r"^(The\s+)?Hong Kong University of Science and Technology$": "The Hong Kong University of Science and Technology",
    r"^The University of Hong Kong$": "University of Hong Kong",
    r"University of Sao Paulo": "University of São Paulo",
    r"^Birla Institute of Technology and Science, Pilani - Goa Campus$": "Birla Institute of Technology and Science",
    r"^École Polytechnique Fédérale de Lausanne$": "Ecole Polytechnique Federale de Lausanne",
    # Asia / Europe shortcuts
    r"\bSJTU\b": "Shanghai Jiao Tong University",
    r"\bUSTC\b": "University of Science and Technology of China",
    r"\bBITS?\s*Pilani\b": "Birla Institute of Technology and Science",
    r"\bPOSTECH\b": "Pohang University of Science and Technology",
    r"\bEPFL\b": "Ecole Polytechnique Federale de Lausanne",
    r"^Harvard College$": "Harvard University",
}

MISSING_PAT = re.compile(r"(not\s*(found|available)|^n/?a$|unknown)", re.I)


def canonicalise_school(inst: str) -> str:
    inst = inst.strip()
    if not inst or MISSING_PAT.search(inst):
        return ""

    inst = inst.replace("–", "-").replace("—", "-")
    inst = re.sub(r"^The\s+", "", inst, flags=re.I)
    inst = inst.split(";")[0].strip()  # keep first institution if semicolon-separated

    # expand common abbreviations
    for pat, repl in ALIASES.items():
        if re.search(pat, inst, flags=re.I):
            inst = re.sub(pat, repl, inst, flags=re.I)
            break

    # keep only the first institution in “X & Y” or “X and Y” (when Y looks like an institution)
    inst = inst.split("&")[0].strip()
    inst = re.split(r"\s+and\s+(?=(University|College|Institut|School|Polytechnic))", inst, maxsplit=1)[0].strip()

    # remove balanced (…) and dangling “( …”
    inst = re.sub(r"\([^)]*\)", " ", inst)  # balanced
    inst = re.sub(r"\s*\(.*$", "", inst)  # unmatched
    inst = re.sub(r"\s+", " ", inst).strip()

    # trim trailing “, Country / City / Campus” except UC & U‑Maryland
    if not inst.startswith(("University of California,", "University of Maryland,")):
        inst = re.sub(r",\s*[A-Z][A-Za-z.\s]+$", "", inst).strip()

    return inst


def parse_processed_lines(path: Path) -> Iterator[Tuple[str, str]]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if "|" not in line:
            continue
        name, school = [part.strip() for part in line.split("|", 1)]
        if school:
            yield name, school


def tally_schools(
    input_path: Path,
) -> Tuple[Counter, int, int, List[Tuple[str, str, str]]]:
    """Return counts plus dedupe stats.

    - skip exact duplicate names (counts same person once)
    - record conflicts where the same name is paired with different schools
    - track missing/unknown school lines
    """
    counter: Counter = Counter()
    seen_names: Dict[str, str] = {}
    skipped_duplicates = 0
    skipped_missing = 0
    conflicts: List[Tuple[str, str, str]] = []

    for name, school in parse_processed_lines(input_path):
        canon = canonicalise_school(school)
        if not canon:
            skipped_missing += 1
            continue

        if name in seen_names:
            if seen_names[name] == canon:
                skipped_duplicates += 1
                continue
            conflicts.append((name, seen_names[name], canon))
            continue

        seen_names[name] = canon
        counter[canon] += 1

    return counter, skipped_duplicates, skipped_missing, conflicts


def save_counts(counter: Counter, output_path: Path) -> None:
    lines = ["School | Student Count", "- | -"]
    for school, count in counter.most_common():
        lines.append(f"{school} | {count}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Count students per school from processed Stanford data.")
    parser.add_argument("input_file", type=Path, help="Processed merged file (Name | School per line)")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Where to save the counts table (default: <input>_counts.txt)",
    )
    args = parser.parse_args()

    output_path = args.output or args.input_file.with_name(
        f"{args.input_file.stem}_counts{args.input_file.suffix}"
    )

    counts, skipped_duplicates, skipped_missing, conflicts = tally_schools(args.input_file)
    save_counts(counts, output_path)
    print(f"Wrote counts for {len(counts)} schools to {output_path}")
    if skipped_duplicates:
        print(f"Skipped {skipped_duplicates} duplicate entr{'y' if skipped_duplicates == 1 else 'ies'} by name.", file=sys.stderr)
    if skipped_missing:
        print(f"Skipped {skipped_missing} entr{'y' if skipped_missing == 1 else 'ies'} with missing/unknown school.", file=sys.stderr)
    if conflicts:
        print("Conflicting school entries for the same name (kept first occurrence):", file=sys.stderr)
        for name, first, other in conflicts:
            print(f"  {name}: '{first}' vs '{other}'", file=sys.stderr)


if __name__ == "__main__":
    main()
