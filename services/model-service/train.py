#!/usr/bin/env python3
"""
SageMaker Training Script for News Categorization
"""
import argparse
import json
import os
import pickle
from pathlib import Path

import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, accuracy_score, f1_score


def load_data(data_dir):
    """Load and preprocess training data."""
    data_path = Path(data_dir) / 'News_Category_Dataset_v3.json'

    print(f"Loading data from {data_path}")

    # Load JSON data
    data = []
    with open(data_path, 'r') as f:
        for line in f:
            data.append(json.loads(line))

    df = pd.DataFrame(data)
    print(f"Loaded {len(df)} articles")
    print(f"Categories: {df['category'].nunique()}")

    # Combine headline and short_description
    df['text'] = df['headline'] + ' ' + df['short_description'].fillna('')

    return df


def train_model(args):
    """Train the model."""
    print("Starting training...")
    print(f"Arguments: {args}")

    # Load data
    df = load_data(args.train)

    # Prepare features and labels
    X = df['text']
    y = df['category']

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"Training set: {len(X_train)} samples")
    print(f"Test set: {len(X_test)} samples")

    # Create pipeline
    max_features = int(args.max_features)
    print(f"Building {args.model_type} model with max_features={max_features}")

    if args.model_type == 'logistic_regression':
        model = Pipeline([
            ('tfidf', TfidfVectorizer(max_features=max_features, stop_words='english')),
            ('clf', LogisticRegression(max_iter=1000, random_state=42))
        ])
    else:
        raise ValueError(f"Unknown model type: {args.model_type}")

    # Train model
    print("Training model...")
    model.fit(X_train, y_train)

    # Evaluate
    print("Evaluating model...")
    y_pred = model.predict(X_test)

    accuracy = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, average='weighted')

    print(f"Accuracy: {accuracy:.4f}")
    print(f"F1 Score: {f1:.4f}")

    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))

    # Save model
    model_dir = Path(args.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    model_path = model_dir / 'model.pkl'
    print(f"Saving model to {model_path}")

    # Save in the format expected by inference service
    model_data = {
        'pipeline': model,
        'preprocessor': model.named_steps['tfidf'],
        'categories': list(model.classes_),
        'metrics': {
            'accuracy': float(accuracy),
            'f1_score': float(f1)
        }
    }

    with open(model_path, 'wb') as f:
        pickle.dump(model_data, f)

    print("Training complete!")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    # SageMaker specific arguments
    parser.add_argument('--model-dir', type=str, default=os.environ.get('SM_MODEL_DIR', '/opt/ml/model'))
    parser.add_argument('--train', type=str, default=os.environ.get('SM_CHANNEL_TRAINING', '/opt/ml/input/data/training'))

    # Hyperparameters
    parser.add_argument('--model_type', type=str, default='logistic_regression')
    parser.add_argument('--max_features', type=str, default='10000')
    parser.add_argument('--include_feedback', type=str, default='false')

    args = parser.parse_args()

    try:
        train_model(args)
    except Exception as e:
        print(f"Training failed: {e}")
        import traceback
        traceback.print_exc()
        raise
