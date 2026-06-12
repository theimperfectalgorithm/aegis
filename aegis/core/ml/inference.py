
"""
Inference module for AEGIS Core ML.
Handles inference and prediction using trained models.

ML v1 is a filter, not a predictor: it only rejects low-quality signals, improving prop firm survival.
This module coordinates feature engineering and model inference, returning a confidence score [0, 1].
"""

from aegis.core.ml.base_model import BaseMLModel



class InferenceEngine:
	"""
	Coordinates feature engineering and model inference for trade scoring.
	ML v1 is intentionally simple: it filters out low-quality signals using a confidence score.
	"""

	def __init__(self, feature_engineer=None, model_path="ml_model_v1.joblib"):
		"""
		Initialize the InferenceEngine and dependencies.
		Args:
			feature_engineer: FeatureEngineer instance (optional)
			model_path (str): Path to the trained model artifact.
		"""
		self.feature_engineer = feature_engineer
		self.model = BaseMLModel(model_path)
		self.model.load_model()

	def score_trade(self, market_data, signal_context):
		"""
		Score a trade opportunity using feature engineering and model inference.
		Args:
			market_data: Raw market data input.
			signal_context: Additional context for the trade signal.
		Returns:
			float: Confidence score between 0 and 1 (probability of positive outcome).
		"""
		# 1. Build features using FeatureEngineer
		if self.feature_engineer is not None:
			features = self.feature_engineer.build_features(market_data, signal_context)
		else:
			features = signal_context['features']  # fallback if already built
		# 2. Load trained model (already loaded in __init__)
		# 3. Return confidence score
		score = self.model.predict(features)
		return score