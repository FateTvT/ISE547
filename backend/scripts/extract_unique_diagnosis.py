"""Extract unique values from a diagnosis-like CSV column."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

DEFAULT_INPUT = Path(
    "scripts/data/updated_result_with_BERT_eval_120_cleaned_cleaned.csv"
)
DEFAULT_COLUMN = "Diagnosis"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for unique diagnosis extraction."""

    parser = argparse.ArgumentParser(
        description="Extract unique values from diagnosis/diangosis column in a CSV."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Input CSV path. Default: {DEFAULT_INPUT}",
    )
    parser.add_argument(
        "--column",
        type=str,
        default=DEFAULT_COLUMN,
        help=f"Column name to extract unique values from. Default: {DEFAULT_COLUMN}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output txt path for unique values (one per line).",
    )
    return parser.parse_args()


def _resolve_script_relative_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    cwd_candidate = path.resolve()
    if cwd_candidate.exists():
        return cwd_candidate

    script_dir = Path(__file__).parent
    backend_candidate = (script_dir.parent / path).resolve()
    if backend_candidate.exists():
        return backend_candidate

    return cwd_candidate


def _normalize_column_name(name: str) -> str:
    return "".join(ch for ch in name.strip().lower() if ch.isalnum())


def resolve_column_name(fieldnames: list[str], requested_column: str) -> str:
    """Resolve an existing CSV column with typo and case-insensitive fallback."""

    if requested_column in fieldnames:
        return requested_column

    lookup = {name.strip().lower(): name for name in fieldnames}
    normalized_requested = requested_column.strip().lower()
    if normalized_requested in lookup:
        return lookup[normalized_requested]

    normalized_lookup = {_normalize_column_name(name): name for name in fieldnames}
    normalized_requested_compact = _normalize_column_name(requested_column)
    if normalized_requested_compact in normalized_lookup:
        return normalized_lookup[normalized_requested_compact]

    alias_map = {
        "diagnosis": ["Diagnosis", "Diagnosis_mapped"],
        "diangosis": ["Diagnosis", "Diagnosis_mapped"],
        "category": ["Diagnosis Category_mapped", "Diagnosis Category"],
        "catgory": ["Diagnosis Category_mapped", "Diagnosis Category"],
    }
    for alias in alias_map.get(normalized_requested, []):
        if alias in fieldnames:
            return alias

    for alias in ("diagnosis", "diangosis", "category", "catgory"):
        if alias in lookup:
            return lookup[alias]

    available = ", ".join(fieldnames)
    raise KeyError(
        f"Column '{requested_column}' not found. Available columns: {available}"
    )


def extract_unique_values(
    input_path: Path, requested_column: str
) -> tuple[str, list[str]]:
    """Extract sorted unique non-empty values from target CSV column."""

    with input_path.open("r", encoding="utf-8-sig", newline="") as infile:
        reader = csv.DictReader(infile)
        if reader.fieldnames is None:
            raise ValueError("Input CSV has no header.")
        column_name = resolve_column_name(reader.fieldnames, requested_column)

        unique_values = {
            (row.get(column_name, "") or "").strip()
            for row in reader
            if (row.get(column_name, "") or "").strip()
        }

    return column_name, sorted(unique_values)


def main() -> None:
    """Run unique diagnosis extraction workflow."""

    args = parse_args()
    input_path = _resolve_script_relative_path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    column_name, unique_values = extract_unique_values(input_path, args.column)
    print(f"Input: {input_path}")
    print(f"Column: {column_name}")
    print(f"Unique count: {len(unique_values)}")
    print("Unique values:")
    for value in unique_values:
        print(f"- {value}")

    if args.output is not None:
        output_path = _resolve_script_relative_path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(unique_values) + "\n", encoding="utf-8")
        print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
