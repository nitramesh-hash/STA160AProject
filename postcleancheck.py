import argparse
import json
import re
from pathlib import Path
import pandas as pd

TERM_MONTH = {"fall": 9, "winter": 1, "spring": 3, "summer": 6}

# ---------- helpers ----------
def parse_effective_ts(text: str):
    """Extract a comparable timestamp from various 'effective' wordings in Description."""
    if not isinstance(text, str):
        return pd.NaT
    # Season + year
    m = re.search(r"(?i)\b(fall|winter|spring|summer)\s+(\d{4})\b", text)
    if m:
        season, year = m.group(1).lower(), int(m.group(2))
        return pd.Timestamp(year=year, month=TERM_MONTH[season], day=1)
    # Month + year
    m = re.search(
        r"(?i)\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
        r"dec(?:ember)?)\s+(\d{4})\b", text
    )
    if m:
        try:
            return pd.to_datetime(f"1 {m.group(1)} {m.group(2)}", errors="raise")
        except Exception:
            pass
    # Academic year like 2025–26 -> Fall of first year
    m = re.search(r"\b(20\d{2})\s*[–-]\s*(\d{2})\b", text)
    if m:
        return pd.Timestamp(year=int(m.group(1)), month=9, day=1)
    # Bare year
    m = re.search(r"\b(20\d{2})\b", text)
    if m:
        return pd.Timestamp(year=int(m.group(1)), month=1, day=1)
    return pd.NaT


def extract_latest_prereq_from_description(desc: str):
    """
    Return the newest 'Prerequisite(s): ...' clause from Description.
    If multiple versions exist and 'effective ...' appears, prefer the clause after the last 'effective'.
    """
    if not isinstance(desc, str):
        return None

    # capture all prereq clauses up to a period or newline
    clauses = [
        (m.start(), m.group(1).strip())
        for m in re.finditer(r"(?:Prerequisite\(s\)|Prerequisite)\s*:\s*([^.\n]+)", desc, flags=re.IGNORECASE)
    ]
    if not clauses:
        return None

    eff_positions = [m.start() for m in re.finditer(r"\beffective\s*(?:from)?\b", desc, flags=re.IGNORECASE)]
    if eff_positions:
        anchor = max(eff_positions)
        after = [c for c in clauses if c[0] > anchor]
        chosen = after[-1][1] if after else clauses[-1][1]
    else:
        chosen = clauses[-1][1]

    # normalize spacing and course codes (e.g., MAT021A -> MAT 021A)
    chosen = re.sub(r"\s+", " ", chosen).strip()
    chosen = re.sub(r"\b([A-Z]{2,4})\s*0?(\d{2,3}[A-Z]?)\b", r"\1 \2", chosen)
    return chosen


def update_prerequisites(df: pd.DataFrame, overrides: dict | None = None) -> pd.DataFrame:
    """
    Takes a course DataFrame, picks current rows per Course Code, and ensures
    'Prerequisites' reflect the newest clause from Description (if present).
    """
    required_cols = {"Course Code", "Title", "Description", "Prerequisites"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {sorted(missing)}")

    df = df.copy()
    # compute 'current' per course code
    desc = df["Description"].astype(str)
    df["effective_from_ts"] = desc.apply(parse_effective_ts)
    df["has_effective"] = desc.str.contains(r"(?i)\beffective\s*(?:from)?\b")

    df = df.sort_values(by=["Course Code", "has_effective", "effective_from_ts"], ascending=[True, True, True])
    current = df.groupby("Course Code", as_index=False).tail(1).reset_index(drop=True)

    # replace prerequisites if a newer clause exists in Description
    desc_pr = current["Description"].astype(str).apply(extract_latest_prereq_from_description)
    replace_mask = desc_pr.notna() & (desc_pr.str.len() > 0)
    current.loc[replace_mask, "Prerequisites"] = desc_pr[replace_mask]

    # apply user overrides last (highest priority)
    if overrides:
        for code, prereq in overrides.items():
            mask = current["Course Code"].astype(str).str.fullmatch(code)
            current.loc[mask, "Prerequisites"] = prereq

    # remove helper cols
    current = current.drop(columns=["effective_from_ts", "has_effective"], errors="ignore")
    return current


def process_one_file(in_path: Path, out_dir: Path, overrides: dict | None):
    df = pd.read_csv(in_path)
    updated = update_prerequisites(df, overrides=overrides)

    out_dir.mkdir(parents=True, exist_ok=True)
    # default output name: <basename>_current_with_prereqs_final.csv
    stem = in_path.stem
    out_path = out_dir / f"{stem}_current_with_prereqs_final.csv"
    updated.to_csv(out_path, index=False)
    print(f"✅ Saved: {out_path}")
    return out_path


# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser(description="Update course CSV(s) so 'Prerequisites' reflect newest catalog versions.")
    ap.add_argument("--input", "-i", required=True,
                    help="Input CSV path or a directory containing CSVs.")
    ap.add_argument("--output-dir", "-o", default="datasets",
                    help="Directory to write updated CSVs (default: datasets).")
    ap.add_argument("--overrides", "-O", default=None,
                    help="Optional JSON file mapping 'Course Code' -> 'Prerequisites' for authoritative fixes.")
    args = ap.parse_args()

    input_path = Path(args.input)
    out_dir = Path(args.output_dir)
    overrides = {}
    if args.overrides:
        with open(args.overrides, "r", encoding="utf-8") as f:
            overrides = json.load(f)

    if input_path.is_dir():
        for p in sorted(input_path.glob("*.csv")):
            process_one_file(p, out_dir, overrides)
    else:
        process_one_file(input_path, out_dir, overrides)


if __name__ == "__main__":
    main()
