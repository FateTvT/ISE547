"""Build a cleaned and stratified evaluation sample from a CSV file.

Run this script as a module with `uv run -m scripts.extract_sample`.
"""

from __future__ import annotations

import argparse
import csv
import random
import re
import string
from collections import Counter
from pathlib import Path


DEFAULT_INPUT = Path("scripts/data/updated_result_with_BERT.csv")
DEFAULT_OUTPUT = Path("scripts/data/updated_result_with_BERT_eval_120.csv")
DEFAULT_SEED = 42
DUPLICATE_KEY_FIELDS = ("age", "gender", "Patient History", "symptoms", "Diagnosis")
CATEGORY_FIELD = "Diagnosis Category"
DIAGNOSIS_FIELD = "Diagnosis"
HISTORY_FIELD = "Patient History"
INVALID_CATEGORIES = {"", "unknown"}
CATEGORY_QUOTAS = {
    "Hip-related disorders": 50,
    "Musculoskeletal disorders": 25,
    "Bone-related disorders": 20,
    "Other": 15,
    "Spinal disorders": 10,
}


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for CSV sampling."""
    parser = argparse.ArgumentParser(
        description=(
            "Clean data with fixed protocol and build a stratified 120-row "
            "evaluation set."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Input CSV path. Default: {DEFAULT_INPUT}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output CSV path. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Random seed for reproducibility. Default: {DEFAULT_SEED}",
    )
    return parser.parse_args()


def normalize_text(text: str) -> str:
    """Normalize text for leakage checks."""
    lowered = text.lower()
    no_punct = lowered.translate(str.maketrans({c: " " for c in string.punctuation}))
    compact = re.sub(r"\s+", " ", no_punct).strip()
    return compact


def clean_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], Counter[str]]:
    """Clean rows with fixed deduplication and leakage-removal protocol."""
    stats = Counter()

    deduplicated_rows: list[dict[str, str]] = []
    seen_keys: set[tuple[str, ...]] = set()
    for row in rows:
        key = tuple(
            (row.get(field, "") or "").strip() for field in DUPLICATE_KEY_FIELDS
        )
        if key in seen_keys:
            stats["removed_duplicate"] += 1
            continue
        seen_keys.add(key)
        deduplicated_rows.append(row)

    valid_label_rows: list[dict[str, str]] = []
    for row in deduplicated_rows:
        diagnosis = (row.get(DIAGNOSIS_FIELD, "") or "").strip()
        category = (row.get(CATEGORY_FIELD, "") or "").strip()
        if not diagnosis:
            stats["removed_empty_diagnosis"] += 1
            continue
        if category.lower() in INVALID_CATEGORIES:
            stats["removed_invalid_category"] += 1
            continue
        valid_label_rows.append(row)

    cleaned_rows: list[dict[str, str]] = []
    for row in valid_label_rows:
        diagnosis_norm = normalize_text((row.get(DIAGNOSIS_FIELD, "") or "").strip())
        history_norm = normalize_text((row.get(HISTORY_FIELD, "") or "").strip())
        if diagnosis_norm and diagnosis_norm in history_norm:
            stats["removed_leakage"] += 1
            continue
        cleaned_rows.append(row)

    return cleaned_rows, stats


def stratified_sample(rows: list[dict[str, str]], seed: int) -> list[dict[str, str]]:
    """Sample rows with fixed category quotas."""
    rows_by_category: dict[str, list[dict[str, str]]] = {k: [] for k in CATEGORY_QUOTAS}
    for row in rows:
        category = (row.get(CATEGORY_FIELD, "") or "").strip()
        if category in rows_by_category:
            rows_by_category[category].append(row)

    shortages = [
        f"{category}: need {quota}, available {len(rows_by_category[category])}"
        for category, quota in CATEGORY_QUOTAS.items()
        if len(rows_by_category[category]) < quota
    ]
    if shortages:
        joined = "; ".join(shortages)
        raise ValueError(f"Not enough rows for fixed quotas after cleaning: {joined}")

    rng = random.Random(seed)
    sampled_rows: list[dict[str, str]] = []
    for category, quota in CATEGORY_QUOTAS.items():
        sampled_rows.extend(rng.sample(rows_by_category[category], quota))
    rng.shuffle(sampled_rows)
    return sampled_rows


def build_eval_sample(
    input_path: Path, output_path: Path, seed: int
) -> tuple[int, int, Counter[str], Counter[str]]:
    """Build cleaned and stratified evaluation sample CSV."""

    with input_path.open("r", encoding="utf-8", newline="") as infile:
        reader = csv.DictReader(infile)
        if reader.fieldnames is None:
            raise ValueError("input CSV is empty")
        fieldnames = reader.fieldnames
        rows = list(reader)

    total_rows = len(rows)
    cleaned_rows, clean_stats = clean_rows(rows)
    sampled_rows = stratified_sample(cleaned_rows, seed)
    sampled_distribution = Counter(
        (row.get(CATEGORY_FIELD, "") or "").strip() for row in sampled_rows
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sampled_rows)

    return total_rows, len(cleaned_rows), clean_stats, sampled_distribution


def main() -> None:
    """Run CSV row sampling workflow."""
    args = parse_args()
    total_rows, cleaned_count, clean_stats, sampled_distribution = build_eval_sample(
        input_path=args.input,
        output_path=args.output,
        seed=args.seed,
    )
    print(f"Input: {args.input}")
    print(f"Output: {args.output}")
    print(f"Total input rows: {total_rows}")
    print(f"Rows after cleaning: {cleaned_count}")
    print(
        "Removed rows - duplicates: "
        f"{clean_stats['removed_duplicate']}, empty diagnosis: "
        f"{clean_stats['removed_empty_diagnosis']}, invalid category: "
        f"{clean_stats['removed_invalid_category']}, leakage: "
        f"{clean_stats['removed_leakage']}"
    )
    print("Sample distribution:")
    for category, quota in CATEGORY_QUOTAS.items():
        print(f"  - {category}: {sampled_distribution.get(category, 0)}")


if __name__ == "__main__":
    main()
