"""
AEGIS Backtest Runner
Runs backtests for strategy-only and ML-filtered trading.
"""
import argparse
import yaml
from aegis.backtesting.engine import BacktestEngine
from aegis.backtesting import reports
import os
from datetime import datetime


def parse_args():
    parser = argparse.ArgumentParser(description="AEGIS Backtest Runner")
    parser.add_argument('--start_date', type=str, required=True, help='Backtest start date (YYYY-MM-DD)')
    parser.add_argument('--end_date', type=str, required=True, help='Backtest end date (YYYY-MM-DD)')
    parser.add_argument('--symbols', type=str, nargs='+', required=True, help='List of symbols to backtest')
    parser.add_argument('--enable_ml', action='store_true', help='Enable ML filtering in trading pipeline')
    parser.add_argument('--trading_mode', type=str, default='DATA_COLLECTION', help='Trading mode (default: DATA_COLLECTION)')
    parser.add_argument('--config', type=str, default='configs/main_agent.yaml', help='Path to main agent config')
    return parser.parse_args()


def load_config(path):
    with open(path, 'r') as f:
        return yaml.safe_load(f)


def save_results(results, label, out_dir="backtest_results"):
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{label}_results_{ts}.yaml"
    with open(os.path.join(out_dir, fname), 'w') as f:
        yaml.safe_dump(results, f)
    print(f"Results saved to {os.path.join(out_dir, fname)}")


def main():
    args = parse_args()
    config = load_config(args.config)
    config['enable_ml'] = args.enable_ml
    config['backtest_mode'] = True
    config['trading_mode'] = args.trading_mode
    config['symbols'] = args.symbols
    config['start_date'] = args.start_date
    config['end_date'] = args.end_date

    # Baseline: strategy-only
    config['enable_ml'] = False
    print("Running baseline (strategy-only)...")
    engine = BacktestEngine(config)
    baseline_results = engine.run()
    save_results(baseline_results, label="baseline")

    # ML-filtered
    config['enable_ml'] = True
    print("Running ML-filtered...")
    engine_ml = BacktestEngine(config)
    ml_results = engine_ml.run()
    save_results(ml_results, label="ml")

    # Comparison
    print("Comparing results...")
    reports.compare_equity_curves(baseline_results, ml_results)
    reports.compare_drawdowns(baseline_results, ml_results)
    reports.compare_trade_stats(baseline_results, ml_results)

if __name__ == "__main__":
    main()
