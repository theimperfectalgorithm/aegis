
"""
Training Pipeline for AEGIS Core ML.
Handles training workflows for machine learning models.

ML v1 is a simple, explainable filter to reject low-quality strategy signals.
It uses only a few features and a conservative classifier to avoid overfitting.
This improves prop firm survival by reducing bad trades, not by predicting profits.
"""

import pandas as pd
from sklearn.preprocessing import LabelEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
import numpy as np



class TrainingPipeline:

		def retrain_if_improved(self, trade_logs, model_type='logistic', validation_split=0.2, logger=None):
			"""
			Retrain ML model on new trade logs, compare to current, and replace only if metrics improve.
			Args:
				trade_logs: List of trade log dicts
				model_type: 'logistic' or 'rf'
				validation_split: Fraction for validation set
				logger: Optional logger for logging decisions
			Returns:
				dict: {'retrained': bool, 'old_acc': float, 'new_acc': float, 'decision': str}
			"""
			import numpy as np
			import logging as pylogging
			log = logger or pylogging.getLogger("AEGIS.ML.Retraining")
			if len(trade_logs) < 50:
				log.warning("Not enough data for retraining. Skipping.")
				return {'retrained': False, 'decision': 'not_enough_data'}
			# Prepare dataset
			X, y = self.prepare_dataset(trade_logs)
			# Split into train/val
			n = len(X)
			idx = np.arange(n)
			np.random.shuffle(idx)
			split = int(n * (1 - validation_split))
			train_idx, val_idx = idx[:split], idx[split:]
			X_train, y_train = X.iloc[train_idx], y[train_idx]
			X_val, y_val = X.iloc[val_idx], y[val_idx]
			# Evaluate current model
			old_acc = None
			if self.model is not None:
				try:
					old_acc = accuracy_score(y_val, self.model.predict(X_val))
				except Exception:
					old_acc = None
			# Train new model
			if model_type == 'rf':
				new_model = RandomForestClassifier(n_estimators=25, max_depth=3, random_state=42)
			else:
				new_model = LogisticRegression(max_iter=200, random_state=42)
			new_model.fit(X_train, y_train)
			new_acc = accuracy_score(y_val, new_model.predict(X_val))
			# Compare and decide
			if (old_acc is None) or (new_acc > old_acc):
				self.model = new_model
				log.info(f"ML retraining: Model replaced. Old acc: {old_acc}, New acc: {new_acc}")
				return {'retrained': True, 'old_acc': old_acc, 'new_acc': new_acc, 'decision': 'model_replaced'}
			else:
				log.info(f"ML retraining: Model NOT replaced. Old acc: {old_acc}, New acc: {new_acc}")
				return {'retrained': False, 'old_acc': old_acc, 'new_acc': new_acc, 'decision': 'model_retained'}
	"""
	Prepares datasets, trains/updates the shared base model, and evaluates model performance.
	ML v1 is intentionally simple: it filters out low-quality signals using a few robust features.
	This is to avoid overfitting and ensure explainability for prop firm compliance.
	"""

	def __init__(self):
		"""
		Initialize the TrainingPipeline and dataset/model configuration.
		"""
		self.label_encoders = {}
		self.model = None

	def prepare_dataset(self, trade_logs):
		"""
		Prepare a pandas DataFrame from trade logs for model training.
		Only uses simple, robust features for ML v1.
		Args:
			trade_logs: List of dicts from TradeLogger, each with keys:
				- breakout_distance
				- session_high
				- session_low
				- timestamp
				- symbol
				- direction ("BUY"/"SELL")
				- outcome ("win"/"loss" or 1/0)
		Returns:
			X (pd.DataFrame): Features
			y (np.ndarray): Target (1 for profit, 0 for loss)
		"""
		df = pd.DataFrame(trade_logs)
		# Feature: breakout_distance (float)
		# Feature: session_range_size (float)
		df['session_range_size'] = df['session_high'] - df['session_low']
		# Feature: hour_of_day (int)
		df['hour_of_day'] = pd.to_datetime(df['timestamp']).dt.hour
		# Feature: symbol (label-encoded)
		le_symbol = LabelEncoder()
		df['symbol_enc'] = le_symbol.fit_transform(df['symbol'])
		self.label_encoders['symbol'] = le_symbol
		# Feature: direction (binary: 1=BUY, 0=SELL)
		df['direction_bin'] = (df['direction'] == 'BUY').astype(int)
		# Target: outcome (1 for profit, 0 for loss)
		if df['outcome'].dtype == object:
			df['outcome_bin'] = (df['outcome'].str.lower() == 'win').astype(int)
		else:
			df['outcome_bin'] = df['outcome']
		features = ['breakout_distance', 'session_range_size', 'hour_of_day', 'symbol_enc', 'direction_bin']
		X = df[features]
		y = df['outcome_bin'].values
		return X, y

	def train_model(self, dataset, model_type='logistic'):
		"""
		Train a simple, explainable classifier to filter low-quality signals.
		Args:
			dataset: Tuple (X, y) from prepare_dataset
			model_type: 'logistic' or 'rf' (random forest)
		Returns:
			Trained model
		"""
		X, y = dataset
		if model_type == 'rf':
			model = RandomForestClassifier(n_estimators=25, max_depth=3, random_state=42)
		else:
			model = LogisticRegression(max_iter=200, random_state=42)
		model.fit(X, y)
		self.model = model
		return model

	def evaluate_model(self, dataset):
		"""
		Evaluate the trained model on a validation or test dataset.
		Args:
			dataset: Tuple (X, y) from prepare_dataset
		Returns:
			dict: Accuracy and classification report
		"""
		X, y = dataset
		if self.model is None:
			raise ValueError("Model not trained yet.")
		y_pred = self.model.predict(X)
		acc = accuracy_score(y, y_pred)
		report = classification_report(y, y_pred, output_dict=True)
		return {'accuracy': acc, 'report': report}