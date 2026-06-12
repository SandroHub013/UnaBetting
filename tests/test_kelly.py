"""Tests for the Kelly criterion formula and edge cases."""
from __future__ import annotations

import pytest
import numpy as np
from pathlib import Path


def kelly_fraction(p: float, odds: float) -> float:
    if odds <= 1.0:
        return 0.0
    b = odds - 1.0
    return (p * b - (1.0 - p)) / b


def effective_kelly(p: float, odds: float, kelly_fraction_mult: float = 0.25,
                    max_stake_pct: float = 0.02, bankroll: float = 1000.0) -> float:
    k = kelly_fraction(p, odds)
    if k <= 0:
        return 0.0
    return bankroll * min(k * kelly_fraction_mult, max_stake_pct)


class TestKellyFormula:
    def test_zero_edge_returns_zero(self):
        for odds in [1.5, 2.0, 3.0, 10.0]:
            p = 1.0 / odds
            k = kelly_fraction(p, odds)
            assert np.isclose(k, 0.0, atol=1e-10)

    def test_negative_edge_returns_negative(self):
        for odds in [2.0, 3.0]:
            p = 1.0 / odds - 0.05
            k = kelly_fraction(p, odds)
            assert k < 0.0

    def test_positive_edge_returns_positive(self):
        k = kelly_fraction(0.55, 2.0)
        assert k > 0.0

    def test_certain_win_at_even_odds(self):
        k = kelly_fraction(1.0, 2.0)
        assert np.isclose(k, 1.0)

    def test_certain_loss(self):
        k = kelly_fraction(0.0, 2.0)
        assert np.isclose(k, -1.0)

    def test_odds_equals_one(self):
        k = kelly_fraction(0.5, 1.0)
        assert k == 0.0

    def test_odds_less_than_one(self):
        k = kelly_fraction(0.5, 0.9)
        assert k == 0.0

    def test_nan_probability_returns_nan(self):
        k = kelly_fraction(float('nan'), 2.0)
        assert np.isnan(k)

    def test_nan_odds_returns_nan(self):
        k = kelly_fraction(0.5, float('nan'))
        assert np.isnan(k)


class TestEffectiveStake:
    def test_fractional_kelly_below_max_stake_cap(self):
        bankroll = 1000.0
        stake = effective_kelly(0.55, 2.0, kelly_fraction_mult=0.25, max_stake_pct=0.05, bankroll=bankroll)
        assert np.isclose(stake, 25.0)

    def test_max_stake_pct_cap(self):
        bankroll = 1000.0
        stake = effective_kelly(0.9, 1.5, kelly_fraction_mult=0.25, max_stake_pct=0.02, bankroll=bankroll)
        assert np.isclose(stake, 20.0)

    def test_zero_edge_no_stake(self):
        stake = effective_kelly(0.5, 2.0, bankroll=1000.0)
        assert stake == 0.0

    def test_negative_edge_no_stake(self):
        stake = effective_kelly(0.4, 2.0, bankroll=1000.0)
        assert stake == 0.0


class TestKellyMonotonicity:
    def test_monotonic_in_probability(self):
        odds = 2.0
        ps = np.linspace(0.51, 0.99, 20)
        kellys = [kelly_fraction(p, odds) for p in ps]
        assert all(k2 > k1 for k1, k2 in zip(kellys, kellys[1:]))

    def test_monotonic_in_odds_for_fixed_edge(self):
        edge = 0.1
        for odds in [1.2, 1.5, 2.0, 3.0, 5.0]:
            p = 1.0 / odds + edge
            k = kelly_fraction(p, odds)
            assert k > 0


class TestBacktestConstants:
    def test_backtest_constants(self):
        from src.models import backtest
        assert backtest.KELLY_FRACTION == 0.25
        assert backtest.MIN_EDGE == 0.03
        assert backtest.MAX_STAKE_PCT == 0.02
        assert backtest.MIN_ODDS == 1.30
        assert backtest.STARTING_BANKROLL == 1000.0
        assert backtest.SEED == 123


class TestConfigConstants:
    def test_config_betting_constants(self):
        import yaml
        config_path = Path(__file__).resolve().parent.parent / "config" / "config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)
        assert config["betting"]["min_value_edge"] == 0.03
        assert config["betting"]["kelly_fraction"] == 0.25
        assert config["betting"]["max_stake"] == 500
        assert config["betting"]["commission_rate"] == 0.0
