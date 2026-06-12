
"""
Base ML Model for AEGIS Core.
Defines shared machine learning model interface.

ML v1 is a simple, explainable filter for low-quality signals.
This model is loaded and used by the inference engine and can be reused across sessions.
"""

import joblib
import os



class BaseMLModel:
	"""
	Shared base ML model for the AEGIS system.
	Handles model loading, saving, and prediction interface using joblib.
	Designed for extensibility and reusability by the inference engine.
	"""

	def __init__(self, model_path="ml_model_v1.joblib"):
		"""
		Initialize the BaseMLModel and model state.
		Args:
			model_path (str): Path to save/load the model artifact.
		"""
		self.model_path = model_path
		self.model = None

	def load_model(self):
		"""
		Load the ML model from disk using joblib.
		Returns:
			Loaded model or None if not found.
		"""
		if os.path.exists(self.model_path):
			self.model = joblib.load(self.model_path)
			return self.model
		else:
			self.model = None
			return None

	def save_model(self, model):
		"""
		Save the ML model to disk using joblib.
		Args:
			model: Trained scikit-learn model.
		"""
		joblib.dump(model, self.model_path)
		self.model = model

	def predict(self, features):
		"""
		Make a prediction using the loaded ML model.
		Args:
			features: Feature vector or DataFrame for prediction.
		Returns:
			Confidence score between 0 and 1 (probability of positive class).
		"""
		if self.model is None:
			raise ValueError("Model not loaded. Call load_model() first.")
		# Predict_proba returns [prob_negative, prob_positive]
		proba = self.model.predict_proba([features])[0]
		return proba[1]