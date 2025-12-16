"""
Model training script for news categorization.

Supports both local training and AWS SageMaker.
"""
import os
import json
import pickle
import argparse
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix
)

from preprocess import load_dataset, prepare_data, TextPreprocessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NewsClassifier:
    """News article classifier using text classification models."""

    SUPPORTED_MODELS = {
        'logistic_regression': LogisticRegression,
        'naive_bayes': MultinomialNB,
        'random_forest': RandomForestClassifier
    }

    def __init__(
        self,
        model_type: str = 'logistic_regression',
        max_features: int = 10000,
        ngram_range: Tuple[int, int] = (1, 2),
        **model_kwargs
    ):
        """
        Initialize the classifier.

        Args:
            model_type: Type of classifier to use
            max_features: Maximum number of TF-IDF features
            ngram_range: N-gram range for TF-IDF
            **model_kwargs: Additional arguments for the model
        """
        if model_type not in self.SUPPORTED_MODELS:
            raise ValueError(f"Unsupported model type: {model_type}")

        self.model_type = model_type
        self.max_features = max_features
        self.ngram_range = ngram_range
        self.model_kwargs = model_kwargs

        # Default model parameters
        default_params = {
            'logistic_regression': {
                'max_iter': 1000,
                'C': 1.0,
                'class_weight': 'balanced',
                'n_jobs': -1
            },
            'naive_bayes': {
                'alpha': 0.1
            },
            'random_forest': {
                'n_estimators': 100,
                'max_depth': 50,
                'class_weight': 'balanced',
                'n_jobs': -1
            }
        }

        params = {**default_params.get(model_type, {}), **model_kwargs}

        # Build pipeline
        self.pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(
                max_features=max_features,
                ngram_range=ngram_range,
                stop_words='english',
                sublinear_tf=True
            )),
            ('classifier', self.SUPPORTED_MODELS[model_type](**params))
        ])

        self.preprocessor: Optional[TextPreprocessor] = None
        self.is_fitted = False
        self.metadata: Dict[str, Any] = {}

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        preprocessor: Optional[TextPreprocessor] = None
    ) -> Dict[str, float]:
        """
        Train the classifier.

        Args:
            X_train: Training texts
            y_train: Training labels
            X_val: Validation texts (optional)
            y_val: Validation labels (optional)
            preprocessor: Text preprocessor with label mapping

        Returns:
            Dictionary of training metrics
        """
        logger.info(f"Training {self.model_type} classifier...")
        logger.info(f"Training samples: {len(X_train)}")

        self.preprocessor = preprocessor
        self.pipeline.fit(X_train, y_train)
        self.is_fitted = True

        # Calculate training metrics
        train_predictions = self.pipeline.predict(X_train)
        metrics = {
            'train_accuracy': accuracy_score(y_train, train_predictions),
            'train_f1': f1_score(y_train, train_predictions, average='weighted')
        }

        # Validation metrics if provided
        if X_val is not None and y_val is not None:
            val_predictions = self.pipeline.predict(X_val)
            metrics['val_accuracy'] = accuracy_score(y_val, val_predictions)
            metrics['val_f1'] = f1_score(y_val, val_predictions, average='weighted')
            metrics['val_precision'] = precision_score(y_val, val_predictions, average='weighted')
            metrics['val_recall'] = recall_score(y_val, val_predictions, average='weighted')

        logger.info(f"Training complete. Metrics: {metrics}")
        return metrics

    def predict(self, texts: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Make predictions.

        Args:
            texts: Array of text strings

        Returns:
            Tuple of (predicted labels, prediction probabilities)
        """
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before making predictions")

        predictions = self.pipeline.predict(texts)
        probabilities = self.pipeline.predict_proba(texts)

        return predictions, probabilities

    def predict_single(self, text: str) -> Dict[str, Any]:
        """
        Make prediction for a single text.

        Args:
            text: Input text

        Returns:
            Dictionary with prediction details
        """
        predictions, probabilities = self.predict(np.array([text]))
        pred_idx = predictions[0]
        probs = probabilities[0]

        # Get top categories
        top_indices = np.argsort(probs)[::-1][:5]
        top_categories = []

        for idx in top_indices:
            category = self.preprocessor.get_category_by_index(idx) if self.preprocessor else str(idx)
            top_categories.append({
                'category': category,
                'confidence': float(probs[idx])
            })

        return {
            'category': self.preprocessor.get_category_by_index(pred_idx) if self.preprocessor else str(pred_idx),
            'confidence': float(probs[pred_idx]),
            'top_categories': top_categories
        }

    def evaluate(
        self,
        X_test: np.ndarray,
        y_test: np.ndarray
    ) -> Dict[str, Any]:
        """
        Evaluate the model on test data.

        Args:
            X_test: Test texts
            y_test: Test labels

        Returns:
            Dictionary of evaluation metrics
        """
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before evaluation")

        predictions, probabilities = self.predict(X_test)

        metrics = {
            'accuracy': float(accuracy_score(y_test, predictions)),
            'precision': float(precision_score(y_test, predictions, average='weighted')),
            'recall': float(recall_score(y_test, predictions, average='weighted')),
            'f1_score': float(f1_score(y_test, predictions, average='weighted')),
        }

        # Per-class metrics
        if self.preprocessor:
            report = classification_report(
                y_test, predictions,
                target_names=self.preprocessor.categories,
                output_dict=True
            )
            metrics['classification_report'] = report

        # Confusion matrix
        cm = confusion_matrix(y_test, predictions)
        metrics['confusion_matrix'] = cm.tolist()

        return metrics

    def save(self, filepath: str) -> None:
        """Save model to file."""
        model_data = {
            'pipeline': self.pipeline,
            'preprocessor': self.preprocessor,
            'model_type': self.model_type,
            'max_features': self.max_features,
            'ngram_range': self.ngram_range,
            'metadata': self.metadata,
            'is_fitted': self.is_fitted
        }

        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)

        logger.info(f"Model saved to {filepath}")

    @classmethod
    def load(cls, filepath: str) -> 'NewsClassifier':
        """Load model from file."""
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)

        classifier = cls(
            model_type=model_data['model_type'],
            max_features=model_data['max_features'],
            ngram_range=model_data['ngram_range']
        )
        classifier.pipeline = model_data['pipeline']
        classifier.preprocessor = model_data['preprocessor']
        classifier.metadata = model_data['metadata']
        classifier.is_fitted = model_data['is_fitted']

        return classifier


def train_model(
    data_path: str,
    output_dir: str,
    model_type: str = 'logistic_regression',
    test_size: float = 0.2,
    val_size: float = 0.1,
    max_features: int = 10000,
    **model_kwargs
) -> Dict[str, Any]:
    """
    Train a news classification model.

    Args:
        data_path: Path to the dataset JSON file
        output_dir: Directory to save model artifacts
        model_type: Type of classifier
        test_size: Test set proportion
        val_size: Validation set proportion
        max_features: Maximum TF-IDF features
        **model_kwargs: Additional model parameters

    Returns:
        Dictionary with training results and metrics
    """
    os.makedirs(output_dir, exist_ok=True)

    logger.info(f"Loading dataset from {data_path}")
    df = load_dataset(data_path)
    logger.info(f"Loaded {len(df)} samples with {df['category'].nunique()} categories")

    logger.info("Preparing data...")
    data_splits, preprocessor = prepare_data(
        df,
        test_size=test_size,
        val_size=val_size
    )

    # Initialize and train classifier
    classifier = NewsClassifier(
        model_type=model_type,
        max_features=max_features,
        **model_kwargs
    )

    train_metrics = classifier.fit(
        X_train=data_splits['X_train'],
        y_train=data_splits['y_train'],
        X_val=data_splits['X_val'],
        y_val=data_splits['y_val'],
        preprocessor=preprocessor
    )

    # Evaluate on test set
    logger.info("Evaluating on test set...")
    test_metrics = classifier.evaluate(
        X_test=data_splits['X_test'],
        y_test=data_splits['y_test']
    )

    # Generate version
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    version = f"v1.0.0_{timestamp}"

    # Add metadata
    classifier.metadata = {
        'version': version,
        'model_type': model_type,
        'training_samples': len(data_splits['X_train']),
        'validation_samples': len(data_splits['X_val']),
        'test_samples': len(data_splits['X_test']),
        'num_categories': len(preprocessor.categories),
        'categories': preprocessor.categories,
        'train_metrics': train_metrics,
        'test_metrics': {k: v for k, v in test_metrics.items() if k != 'confusion_matrix'},
        'trained_at': datetime.now().isoformat(),
        'max_features': max_features
    }

    # Save model
    model_path = os.path.join(output_dir, 'model.pkl')
    classifier.save(model_path)

    # Save label mapping
    label_mapping_path = os.path.join(output_dir, 'label_mapping.json')
    preprocessor.save_label_mapping(label_mapping_path)

    # Save metadata
    metadata_path = os.path.join(output_dir, 'metadata.json')
    with open(metadata_path, 'w') as f:
        json.dump(classifier.metadata, f, indent=2)

    logger.info(f"Training complete. Artifacts saved to {output_dir}")

    return {
        'version': version,
        'model_path': model_path,
        'train_metrics': train_metrics,
        'test_metrics': test_metrics,
        'metadata': classifier.metadata
    }


def main():
    """Main entry point for training script."""
    parser = argparse.ArgumentParser(description='Train news classification model')

    parser.add_argument(
        '--data-path',
        type=str,
        default=os.environ.get('SM_CHANNEL_TRAIN', 'data/News_Category_Dataset_v3.json'),
        help='Path to training data'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=os.environ.get('SM_MODEL_DIR', 'output/model'),
        help='Directory to save model artifacts'
    )
    parser.add_argument(
        '--model-type',
        type=str,
        default='logistic_regression',
        choices=['logistic_regression', 'naive_bayes', 'random_forest'],
        help='Type of classifier to train'
    )
    parser.add_argument(
        '--max-features',
        type=int,
        default=10000,
        help='Maximum number of TF-IDF features'
    )
    parser.add_argument(
        '--test-size',
        type=float,
        default=0.2,
        help='Test set proportion'
    )
    parser.add_argument(
        '--val-size',
        type=float,
        default=0.1,
        help='Validation set proportion'
    )

    args = parser.parse_args()

    results = train_model(
        data_path=args.data_path,
        output_dir=args.output_dir,
        model_type=args.model_type,
        max_features=args.max_features,
        test_size=args.test_size,
        val_size=args.val_size
    )

    print(f"\n=== Training Complete ===")
    print(f"Version: {results['version']}")
    print(f"Test Accuracy: {results['test_metrics']['accuracy']:.4f}")
    print(f"Test F1 Score: {results['test_metrics']['f1_score']:.4f}")


if __name__ == '__main__':
    main()
