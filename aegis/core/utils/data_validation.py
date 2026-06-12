"""
Data Quality & Sanity Checks for AEGIS Trade Logs
Prevents bad data from poisoning ML and alerts Main Agent if data quality degrades.
"""

import logging
from collections import Counter, defaultdict

REQUIRED_FIELDS = [
    'timestamp', 'agent_name', 'account_id', 'market', 'symbol', 'strategy_id',
    'features_snapshot', 'ml_raw_score', 'ml_calibrated_score', 'risk_decision',
    'trade_parameters', 'decision_reason', 'trade_id', 'outcome', 'pnl', 'data_collection_flag'
]

def validate_trade_log_entry(entry):
    """
    Validate a single trade log entry for required fields and types.
    Returns: (is_valid, errors)
    """
    errors = []
    for field in REQUIRED_FIELDS:
        if field not in entry:
            errors.append(f"Missing field: {field}")
    # Optionally, add type checks here
    is_valid = len(errors) == 0
    return is_valid, errors

def detect_missing_fields(logs):
    """
    Detect missing fields in a list of trade log entries.
    Returns: list of (index, missing_fields)
    """
    issues = []
    for i, entry in enumerate(logs):
        missing = [f for f in REQUIRED_FIELDS if f not in entry]
        if missing:
            issues.append({'index': i, 'missing_fields': missing})
    return issues

def detect_duplicate_trades(logs):
    """
    Detect duplicate trades by trade_id in the logs.
    Returns: list of duplicate trade_ids
    """
    trade_ids = [entry.get('trade_id') for entry in logs if 'trade_id' in entry]
    counter = Counter(trade_ids)
    duplicates = [tid for tid, count in counter.items() if tid and count > 1]
    return duplicates

def detect_high_correlation_between_accounts(logs, threshold=0.95):
    """
    Detect high correlation in trade outcomes between accounts (may indicate data leakage or copy trading).
    Returns: list of (account_a, account_b, correlation)
    """
    import numpy as np
    # Group by account
    account_outcomes = defaultdict(list)
    for entry in logs:
        acc = entry.get('account_id')
        outcome = entry.get('outcome')
        if acc and outcome in ('win', 'loss'):
            account_outcomes[acc].append(1 if outcome == 'win' else 0)
    # Compare all pairs
    results = []
    accounts = list(account_outcomes.keys())
    for i in range(len(accounts)):
        for j in range(i+1, len(accounts)):
            a, b = accounts[i], accounts[j]
            arr_a, arr_b = account_outcomes[a], account_outcomes[b]
            if len(arr_a) > 5 and len(arr_b) > 5 and len(arr_a) == len(arr_b):
                corr = np.corrcoef(arr_a, arr_b)[0,1]
                if corr >= threshold:
                    results.append({'account_a': a, 'account_b': b, 'correlation': corr})
    return results
