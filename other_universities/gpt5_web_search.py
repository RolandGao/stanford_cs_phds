import argparse
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from openai import OpenAI

prompt = (
    "The following is a list of current Stanford CS PhDs; find where they attended "
    'undergrad. Each line in the output should be in the format of "{name} | {school}". '
    "Do not output any citations or annotations. Use the web browsing tool. Do not ask followup questions. If the school is not "
    'found, say "unknown" as the school.\n'
)


def call_model(input: str, reasoning_effort: Optional[str] = None) -> str:
    client = OpenAI()
    request = {
        "model": "gpt-5",
        "tools": [
            {"type": "code_interpreter", "container": {"type": "auto"}},
            {"type": "web_search"},
        ],
        "input": input,
    }
    if reasoning_effort:
        request["reasoning"] = {"effort": reasoning_effort}

    response = client.responses.create(**request)
    return response.output_text


def chunked(items: List[str], chunk_size: int) -> Iterable[List[str]]:
    for start in range(0, len(items), chunk_size):
        yield items[start : start + chunk_size]


def get_undergrad_schools(
    people_list: List[str], reasoning_effort: Optional[str] = None
) -> str:
    input_text = prompt + "\n".join(people_list)
    return call_model(input_text, reasoning_effort=reasoning_effort)


def process_names(
    names: List[str],
    output_path: Path,
    chunk_size: int = 10,
    reasoning_effort: Optional[str] = None,
) -> None:
    if not names:
        raise ValueError("No names supplied to process")

    total_chunks = (len(names) + chunk_size - 1) // chunk_size
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        for idx, chunk in enumerate(chunked(names, chunk_size), start=1):
            print(f"Processing chunk {idx}/{total_chunks} with {len(chunk)} names…")
            result = get_undergrad_schools(
                chunk, reasoning_effort=reasoning_effort
            ).strip()
            if result:
                f.write(result + "\n\n")
                f.flush()
    print(f"Saved results to {output_path}")


def process_file(input_path: Path, output_path: Path, chunk_size: int = 10) -> None:
    names = [
        line.strip() for line in input_path.read_text().splitlines() if line.strip()
    ]
    process_names(names, output_path, chunk_size=chunk_size)


def extract_unknown_names(processed_path: Path) -> List[str]:
    names = []
    for line in processed_path.read_text().splitlines():
        if "|" not in line:
            continue
        name, school = [part.strip() for part in line.split("|", 1)]
        if name and school.lower() == "unknown":
            names.append(name)
    return names


def parse_processed_file(path: Path) -> List[Tuple[str, str]]:
    """Parse a processed file into (name, school) tuples, skipping bad lines."""
    entries: List[Tuple[str, str]] = []
    for line in path.read_text().splitlines():
        if "|" not in line:
            continue
        name, school = [part.strip() for part in line.split("|", 1)]
        if name:
            entries.append((name, school))
    return entries


def merge_processed_files(base_path: Path, update_paths: List[Path]) -> List[str]:
    base_entries = parse_processed_file(base_path)

    # Latest non-unknown entry for each name wins.
    updates: Dict[str, str] = {}
    for path in update_paths:
        for name, school in parse_processed_file(path):
            if school and school.lower() != "unknown":
                updates[name] = school

    merged_lines: List[str] = []
    for name, school in base_entries:
        if (not school) or school.lower() == "unknown":
            school = updates.get(name, school)
        merged_lines.append(f"{name} | {school if school else 'unknown'}")
    return merged_lines


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Look up undergrad schools for a list of names."
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Path to a raw names file or a processed file when using --retry-unknowns",
    )
    parser.add_argument(
        "--retry-unknowns",
        action="store_true",
        help="Treat input_file as a processed file, extract names marked unknown, and retry them",
    )
    parser.add_argument(
        "--merge-with",
        type=Path,
        nargs="+",
        help="Processed retry files to merge back into the base processed file",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Where to save the model output (default: <input>_processed.txt)",
    )
    parser.add_argument(
        "-n",
        "--chunk-size",
        type=int,
        default=10,
        help="How many names to send per model call",
    )
    parser.add_argument(
        "-r",
        "--reasoning-effort",
        choices=["low", "medium", "high"],
        help="Reasoning effort to request (default: model default; unknown retries default to high)",
    )
    args = parser.parse_args()

    if args.merge_with:
        if args.retry_unknowns:
            raise ValueError("Use either --merge-with or --retry-unknowns, not both")
        output_path = args.output or args.input_file.with_name(
            f"{args.input_file.stem}_merged{args.input_file.suffix}"
        )
        merged = merge_processed_files(args.input_file, args.merge_with)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(merged) + "\n", encoding="utf-8")
        print(f"Saved merged file to {output_path}")
    elif args.retry_unknowns:
        names = extract_unknown_names(args.input_file)
        if not names:
            raise ValueError(
                "No names marked as unknown were found in the provided file"
            )
        output_path = args.output or args.input_file.with_name(
            f"{args.input_file.stem}_unknown_retry{args.input_file.suffix}"
        )
        reasoning_effort = args.reasoning_effort or "high"
        process_names(
            names,
            output_path,
            chunk_size=args.chunk_size,
            reasoning_effort=reasoning_effort,
        )
    else:
        output_path = args.output or args.input_file.with_name(
            f"{args.input_file.stem}_processed{args.input_file.suffix}"
        )
        process_file(args.input_file, output_path, chunk_size=args.chunk_size)


if __name__ == "__main__":
    main()
