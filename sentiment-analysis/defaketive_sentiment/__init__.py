"""Standalone DeFaketive sentiment and product-risk analyzer."""

from .model import MODEL_VERSION, DefaketiveSentimentModel, ModelSetupError

__all__ = ["MODEL_VERSION", "DefaketiveSentimentModel", "ModelSetupError"]
