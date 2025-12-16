"""
Data preprocessing utilities for news categorization.
"""
import re
import json
from typing import List, Tuple, Dict, Optional
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder


class TextPreprocessor:
    """Text preprocessing for news headlines and descriptions."""

    def __init__(self):
        self.label_encoder = LabelEncoder()
        self.categories: List[str] = []

    def clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        if not isinstance(text, str):
            return ""

        # Convert to lowercase
        text = text.lower()

        # Remove URLs
        text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)

        # Remove special characters but keep apostrophes and basic punctuation
        text = re.sub(r'[^a-zA-Z0-9\s\'\-]', ' ', text)

        # Remove extra whitespace
        text = ' '.join(text.split())

        return text.strip()

    def combine_text(self, headline: str, description: Optional[str] = None) -> str:
        """Combine headline and description for model input."""
        headline = self.clean_text(headline)

        if description:
            description = self.clean_text(description)
            return f"{headline} {description}"

        return headline

    def fit_labels(self, labels: List[str]) -> np.ndarray:
        """Fit label encoder and transform labels."""
        encoded = self.label_encoder.fit_transform(labels)
        self.categories = list(self.label_encoder.classes_)
        return encoded

    def transform_labels(self, labels: List[str]) -> np.ndarray:
        """Transform labels using fitted encoder."""
        return self.label_encoder.transform(labels)

    def inverse_transform_labels(self, encoded: np.ndarray) -> List[str]:
        """Convert encoded labels back to category names."""
        return list(self.label_encoder.inverse_transform(encoded))

    def get_category_by_index(self, index: int) -> str:
        """Get category name by index."""
        if 0 <= index < len(self.categories):
            return self.categories[index]
        raise ValueError(f"Invalid category index: {index}")

    def get_index_by_category(self, category: str) -> int:
        """Get index by category name."""
        if category in self.categories:
            return self.categories.index(category)
        raise ValueError(f"Unknown category: {category}")

    def save_label_mapping(self, filepath: str) -> None:
        """Save label mapping to file."""
        mapping = {
            'categories': self.categories,
            'label_to_index': {cat: idx for idx, cat in enumerate(self.categories)}
        }
        with open(filepath, 'w') as f:
            json.dump(mapping, f, indent=2)

    def load_label_mapping(self, filepath: str) -> None:
        """Load label mapping from file."""
        with open(filepath, 'r') as f:
            mapping = json.load(f)
        self.categories = mapping['categories']
        self.label_encoder.classes_ = np.array(self.categories)


def load_dataset(filepath: str) -> pd.DataFrame:
    """
    Load the HuffPost News Category Dataset.

    Expected format: JSON lines with fields:
    - category: news category
    - headline: article headline
    - short_description: brief description
    - authors: article authors
    - date: publication date
    """
    data = []

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                item = json.loads(line.strip())
                data.append(item)
            except json.JSONDecodeError:
                continue

    df = pd.DataFrame(data)

    # Ensure required columns exist
    required_columns = ['category', 'headline']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    # Fill missing descriptions
    if 'short_description' not in df.columns:
        df['short_description'] = ''
    else:
        df['short_description'] = df['short_description'].fillna('')

    return df


def prepare_data(
    df: pd.DataFrame,
    test_size: float = 0.2,
    val_size: float = 0.1,
    random_state: int = 42
) -> Tuple[Dict[str, np.ndarray], TextPreprocessor]:
    """
    Prepare dataset for training.

    Returns:
        Dictionary with train/val/test splits and the fitted preprocessor
    """
    preprocessor = TextPreprocessor()

    # Combine headline and description
    texts = df.apply(
        lambda row: preprocessor.combine_text(
            row['headline'],
            row.get('short_description', '')
        ),
        axis=1
    ).values

    # Encode labels
    labels = preprocessor.fit_labels(df['category'].values)

    # First split: train+val vs test
    X_temp, X_test, y_temp, y_test = train_test_split(
        texts, labels,
        test_size=test_size,
        random_state=random_state,
        stratify=labels
    )

    # Second split: train vs val
    val_ratio = val_size / (1 - test_size)
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp, y_temp,
        test_size=val_ratio,
        random_state=random_state,
        stratify=y_temp
    )

    return {
        'X_train': X_train,
        'X_val': X_val,
        'X_test': X_test,
        'y_train': y_train,
        'y_val': y_val,
        'y_test': y_test
    }, preprocessor


def get_category_distribution(df: pd.DataFrame) -> Dict[str, int]:
    """Get distribution of categories in dataset."""
    return df['category'].value_counts().to_dict()


def sample_balanced_dataset(
    df: pd.DataFrame,
    samples_per_category: Optional[int] = None,
    random_state: int = 42
) -> pd.DataFrame:
    """
    Create a balanced sample of the dataset.

    Args:
        df: Input dataframe
        samples_per_category: Number of samples per category (min count if None)
        random_state: Random seed

    Returns:
        Balanced dataframe
    """
    category_counts = df['category'].value_counts()

    if samples_per_category is None:
        samples_per_category = category_counts.min()

    balanced_dfs = []
    for category in category_counts.index:
        category_df = df[df['category'] == category]
        if len(category_df) >= samples_per_category:
            sampled = category_df.sample(n=samples_per_category, random_state=random_state)
        else:
            sampled = category_df
        balanced_dfs.append(sampled)

    return pd.concat(balanced_dfs, ignore_index=True).sample(
        frac=1, random_state=random_state
    ).reset_index(drop=True)
