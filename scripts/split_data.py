#!/usr/bin/env python3
"""
split_data.py - Deterministically split tickets_labelled.csv into 20 train and 10 test tickets.
Strictly locks data/test_set.csv using stratified splitting with fixed random_state=42.
The test set MUST NEVER be used for model training or threshold tuning.
"""

from pathlib import Path
import pandas as pd
from sklearn.model_selection import train_test_split


def main():
    root_dir = Path(__file__).resolve().parent.parent
    data_dir = root_dir / "data"
    input_csv = data_dir / "tickets_labelled.csv"

    if not input_csv.exists():
        raise FileNotFoundError(f"Input file not found: {input_csv}")

    df = pd.read_csv(input_csv)
    if len(df) != 30:
        raise ValueError(f"Expected exactly 30 tickets, found {len(df)}")

    print(f"Loaded {len(df)} tickets from {input_csv.name}")
    print("Class distribution before split:")
    print(df["category"].value_counts().to_string())

    # Stratified split: 20 train (66.7%), 10 test (33.3%)
    train_df, test_df = train_test_split(
        df,
        test_size=10,
        random_state=42,
        stratify=df["category"],
    )

    # Sort by ticket_id for clean reproducibility
    train_df = train_df.sort_values("ticket_id").reset_index(drop=True)
    test_df = test_df.sort_values("ticket_id").reset_index(drop=True)

    train_path = data_dir / "train_set.csv"
    test_path = data_dir / "test_set.csv"

    train_df.to_csv(train_path, index=False)
    test_df.to_csv(test_path, index=False)

    print(f"\nSaved {len(train_df)} training tickets to {train_path.name}:")
    print(train_df["category"].value_counts().to_string())

    print(f"\nSaved {len(test_df)} test tickets to {test_path.name} (LOCKED):")
    print(test_df["category"].value_counts().to_string())


if __name__ == "__main__":
    main()
