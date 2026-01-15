"""File I/O utilities for pickle files."""
import pickle
from pathlib import Path
from typing import Any
import pandas as pd


def load_pickle(file_path: Path) -> Any:
    """Load data from a pickle file."""
    with open(file_path, "rb") as f:
        return pickle.load(f)


def save_pickle(data: Any, file_path: Path) -> None:
    """Save data to a pickle file."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "wb") as f:
        pickle.dump(data, f)


def load_spots_dataframe(file_path: Path) -> pd.DataFrame:
    """Load spots DataFrame from pickle file."""
    df = load_pickle(file_path)
    if not isinstance(df, pd.DataFrame):
        raise ValueError(f"Expected DataFrame, got {type(df)}")
    return df


def save_spots_dataframe(df: pd.DataFrame, file_path: Path) -> None:
    """Save spots DataFrame to pickle file."""
    save_pickle(df, file_path)
