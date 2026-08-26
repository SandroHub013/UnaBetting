"""
Tennis Prediction Model - Player Statistics & Feature Engineering
Computes rolling stats, head-to-head records, form, fatigue, and all match features.
"""

import re

import pandas as pd
import numpy as np
from collections import defaultdict


def _num(v):
    """NaN/None-safe numeric coercion. CRITICAL: `np.nan or 0` returns np.nan
    (NaN is truthy in Python), so the old `m.get(k, 0) or 0` pattern let a SINGLE
    stat-less match in a rolling window poison the whole sum -> the entire _50
    serve/return aggregate became NaN. With ~6% of matches lacking serve stats,
    a 50-match window hit a NaN ~95% of the time. `pd.isna` covers None, NaN and NaT."""
    return 0 if pd.isna(v) else v


class PlayerStatsEngine:
    """
    Calculates rolling player statistics for feature engineering.
    All features are computed BEFORE the match (no data leakage).
    """

    def __init__(self):
        self.player_matches = {}  # {player_id: [match_dicts]}
        self.player_surface_matches = {}  # {player_id: {surface: [match_dicts]}}
        self.h2h_records = {}
        # Dated H2H meetings per ordered pair: {(player, opp): [(date, won), ...]}
        # Powers recency-weighted H2H (recent meetings matter more than 10y-old ones).
        self.h2h_history = defaultdict(list)

    def _serve_stats(self, matches, prefix=""):
        """Calculate serve statistics from a list of matches."""
        if not matches:
            return {}

        stats = {}
        total_svpt = sum(_num(m.get(f"{prefix}svpt")) for m in matches)
        total_1st_in = sum(_num(m.get(f"{prefix}1stIn")) for m in matches)
        total_1st_won = sum(_num(m.get(f"{prefix}1stWon")) for m in matches)
        total_2nd_won = sum(_num(m.get(f"{prefix}2ndWon")) for m in matches)
        total_ace = sum(_num(m.get(f"{prefix}ace")) for m in matches)
        total_df = sum(_num(m.get(f"{prefix}df")) for m in matches)
        total_bp_saved = sum(_num(m.get(f"{prefix}bpSaved")) for m in matches)
        total_bp_faced = sum(_num(m.get(f"{prefix}bpFaced")) for m in matches)

        stats["pct_1st_in"] = total_1st_in / total_svpt if total_svpt > 0 else np.nan
        stats["pct_1st_won"] = total_1st_won / total_1st_in if total_1st_in > 0 else np.nan
        svpt_2nd = total_svpt - total_1st_in
        stats["pct_2nd_won"] = total_2nd_won / svpt_2nd if svpt_2nd > 0 else np.nan
        stats["ace_rate"] = total_ace / total_svpt if total_svpt > 0 else np.nan
        stats["df_rate"] = total_df / total_svpt if total_svpt > 0 else np.nan
        stats["bp_save_pct"] = total_bp_saved / total_bp_faced if total_bp_faced > 0 else np.nan

        return stats

    def _return_stats(self, matches):
        """Calculate return statistics from a list of matches."""
        if not matches:
            return {}

        stats = {}
        total_opp_svpt = sum(_num(m.get("opp_svpt")) for m in matches)
        total_opp_1st_won = sum(_num(m.get("opp_1stWon")) for m in matches)
        total_opp_2nd_won = sum(_num(m.get("opp_2ndWon")) for m in matches)
        total_opp_bp_faced = sum(_num(m.get("opp_bpFaced")) for m in matches)
        total_opp_bp_saved = sum(_num(m.get("opp_bpSaved")) for m in matches)
        total_opp_sv_gms = sum(_num(m.get("opp_SvGms")) for m in matches)

        total_opp_pts_won = total_opp_1st_won + total_opp_2nd_won
        stats["return_pts_win_pct"] = (total_opp_svpt - total_opp_pts_won) / total_opp_svpt if total_opp_svpt > 0 else np.nan

        bp_converted = total_opp_bp_faced - total_opp_bp_saved
        stats["bp_convert_pct"] = bp_converted / total_opp_bp_faced if total_opp_bp_faced > 0 else np.nan
        stats["break_rate"] = bp_converted / total_opp_sv_gms if total_opp_sv_gms > 0 else np.nan

        return stats

    def _win_rate(self, matches):
        """Calculate win rate from a list of match results."""
        if not matches:
            return np.nan
        wins = sum(1 for m in matches if m.get("won"))
        return wins / len(matches)

    def _surface_win_rate(self, surface_matches):
        """Win rate on a specific surface."""
        return self._win_rate(surface_matches)

    @staticmethod
    def _length_averages(matches):
        """Mean games, margin, sets, minutes and games-per-set over played matches."""
        scored = [m for m in matches if m.get("total_games") and m["total_games"] > 0]
        sets_list = [m["n_sets"] for m in matches if m.get("n_sets") and m["n_sets"] > 0]
        minutes_list = [m["minutes"] for m in matches if m.get("minutes") and m["minutes"] > 0]
        gps = [m["total_games"] / m["n_sets"] for m in scored
               if m.get("n_sets") and m["n_sets"] > 0]
        return {
            "avg_total_games": np.mean([m["total_games"] for m in scored]) if scored else np.nan,
            "avg_game_margin": (np.mean([abs(m.get("game_diff", 0) or 0) for m in scored])
                                if scored else np.nan),
            "avg_sets_per_match": np.mean(sets_list) if sets_list else np.nan,
            "avg_minutes": np.mean(minutes_list) if minutes_list else np.nan,
            "avg_games_per_set": np.mean(gps) if gps else np.nan,
        }

    @staticmethod
    def _set_shape_stats(matches):
        """How often sets go to a tiebreak or a decider, and how they end."""
        tb_won = sum(m.get("tb_won", 0) or 0 for m in matches)
        tb_sets = tb_won + sum(m.get("tb_lost", 0) or 0 for m in matches)
        total_sets = sum(m.get("n_sets", 0) or 0 for m in matches)
        deciding_sets = sum(1 for m in matches if m.get("went_to_deciding_set"))
        deciding_sets_won = sum(1 for m in matches if m.get("deciding_set_won"))
        matches_vs_lefty = sum(1 for m in matches if m.get("opp_is_lefty"))
        wins_vs_lefty = sum(1 for m in matches if m.get("opp_is_lefty") and m.get("won"))
        return {
            "tiebreak_rate": tb_sets / total_sets if total_sets > 0 else np.nan,
            "tiebreak_win_pct": tb_won / tb_sets if tb_sets > 0 else np.nan,
            "deciding_set_pct": deciding_sets / len(matches) if matches else np.nan,
            "deciding_set_win_pct": (deciding_sets_won / deciding_sets
                                     if deciding_sets > 0 else np.nan),
            "vs_lefty_win_pct": (wins_vs_lefty / matches_vs_lefty
                                 if matches_vs_lefty > 0 else np.nan),
        }

    @staticmethod
    def _hold_pct(matches):
        """Service games won / service games played."""
        sv_gms = sum(_num(m.get("SvGms")) for m in matches)
        if sv_gms <= 0:
            return {"hold_pct": np.nan}
        breaks_against = (sum(_num(m.get("bpFaced")) for m in matches)
                          - sum(_num(m.get("bpSaved")) for m in matches))
        return {"hold_pct": (sv_gms - breaks_against) / sv_gms}

    def _totals_stats(self, matches):
        """Calculate totals-oriented stats: avg games, sets, duration, closeness."""
        if not matches:
            return {}
        stats = self._length_averages(matches)
        stats.update(self._set_shape_stats(matches))
        stats.update(self._hold_pct(matches))
        return stats

    @staticmethod
    def _recent_workload(matches, current_date):
        """Minutes played in the last 14 days, raw and decayed.

        Walks backwards and stops at the first match older than the window,
        which is why `matches` must stay in chronological order.
        """
        minutes_14d = 0
        decay_minutes_14d = 0.0
        for m in reversed(matches):
            m_date = m.get("date")
            if not m_date or pd.isna(m_date):
                continue
            delta = (current_date - m_date).days
            if delta > 14:
                break
            mn = m.get("minutes")
            if mn and not pd.isna(mn):
                minutes_14d += mn
                # Decay: half-life of 4 days. Match 1 day ago = 84% weight. Match 7 days ago = 30% weight.
                decay_minutes_14d += mn * (0.5 ** (delta / 4.0))
        return minutes_14d, decay_minutes_14d

    def _fatigue_features(self, matches, current_date):
        """Calculate fatigue-related features (cumulative load, not just recency)."""
        empty = {"days_since_last": np.nan, "minutes_last_14d": 0}
        if not matches or current_date is None:
            return empty

        # Days since last match
        last_date = matches[-1].get("date")
        if last_date and not pd.isna(last_date):
            days_since = (current_date - last_date).days
        else:
            days_since = np.nan

        # Workload accumulated in recent windows (compounding fatigue with decay).
        minutes_14d, decay_minutes_14d = self._recent_workload(matches, current_date)

        return {
            "days_since_last": days_since,
            "minutes_last_14d": minutes_14d,
            "decay_minutes_14d": decay_minutes_14d,
        }

    def _form_features(self, matches):
        """Momentum / recent-form features — high signal for close (uncertain) matches.

        - form_ewm: exponentially-weighted win rate (recent matches weigh more).
        - current_streak: signed consecutive results (+wins / -losses).
        """
        if not matches:
            return {"form_ewm": np.nan, "current_streak": 0.0}

        results = np.array([1.0 if m.get("won") else 0.0 for m in matches])
        n = len(results)
        # weight 1.0 on the most recent, decaying backwards
        weights = 0.9 ** np.arange(n - 1, -1, -1)
        form_ewm = float(np.dot(weights, results) / weights.sum())

        last_won = matches[-1].get("won")
        streak = 0
        for m in reversed(matches):
            if bool(m.get("won")) == bool(last_won):
                streak += 1
            else:
                break
        current_streak = float(streak if last_won else -streak)

        return {"form_ewm": form_ewm, "current_streak": current_streak}

    def _h2h_features(self, player_id, opponent_id, surface, match_date):
        """Overall, per-surface and last-two-years head-to-head record."""
        h2h = self.h2h_records.get((player_id, opponent_id), {"wins": 0, "losses": 0})
        total_h2h = h2h["wins"] + h2h["losses"]

        h2h_s = self.h2h_records.get((player_id, opponent_id, surface),
                                     {"wins": 0, "losses": 0})
        total_h2h_s = h2h_s["wins"] + h2h_s["losses"]

        hist = self.h2h_history.get((player_id, opponent_id), [])
        recent_meet = [
            won for (d, won) in hist
            if d is not None and not pd.isna(d)
            and (match_date is None or (match_date - d).days <= 730)
        ]
        return {
            "h2h_wins": h2h["wins"],
            "h2h_losses": h2h["losses"],
            "h2h_win_rate": h2h["wins"] / total_h2h if total_h2h > 0 else 0.5,
            "h2h_surface_win_rate": (h2h_s["wins"] / total_h2h_s
                                     if total_h2h_s > 0 else 0.5),
            "h2h_recent_win_rate": (sum(recent_meet) / len(recent_meet)
                                    if recent_meet else 0.5),
            "h2h_recent_n": float(len(recent_meet)),
        }

    def get_player_features(self, player_id, surface, opponent_id=None, match_date=None):
        matches = self.player_matches.get(player_id, [])
        features = {}

        # Technical stats (serve and hold_pct) ONLY for the last 50 matches
        recent_50 = matches[-50:] if len(matches) >= 50 else matches
        features["n_matches_50"] = len(recent_50)

        serve_stats_50 = self._serve_stats(recent_50)
        for k, v in serve_stats_50.items():
            features[f"{k}_50"] = v

        return_stats_50 = self._return_stats(recent_50)
        for k, v in return_stats_50.items():
            features[f"{k}_50"] = v

        totals_stats_50 = self._totals_stats(recent_50)
        features["hold_pct_50"] = totals_stats_50.get("hold_pct", np.nan)

        # Form, general win_rate, and form_ewm ONLY for the last 10 matches
        recent_10 = matches[-10:] if len(matches) >= 10 else matches
        features["win_rate_10"] = self._win_rate(recent_10)
        features["n_matches_10"] = len(recent_10)

        # Surface-specific win rate
        surface_matches = self.player_surface_matches.get(player_id, {}).get(surface, [])
        features["win_rate_surface"] = self._surface_win_rate(surface_matches)
        features["n_matches_surface"] = len(surface_matches)

        if opponent_id:
            features.update(self._h2h_features(player_id, opponent_id, surface, match_date))

        # Momentum / recent form
        features.update(self._form_features(recent_10))

        # Fatigue
        fatigue = self._fatigue_features(matches, match_date)
        features.update(fatigue)

        return features

    @staticmethod
    def _tiebreak_counts(score, is_winner):
        """Tiebreak sets from the score string, which is always winner-POV."""
        if not isinstance(score, str):
            score = ""
        won_by_match_winner = len(re.findall(r'7-6', score))
        lost_by_match_winner = len(re.findall(r'6-7', score))
        total = won_by_match_winner + lost_by_match_winner
        if is_winner:
            return total, won_by_match_winner, lost_by_match_winner
        return total, lost_by_match_winner, won_by_match_winner

    @staticmethod
    def _match_record(row, is_winner):
        """One stored match, already flipped to this player's perspective."""
        prefix = "w_" if is_winner else "l_"
        opp_prefix = "l_" if is_winner else "w_"

        total_games = row.get("total_games", 0) or 0
        game_diff = row.get("game_diff", 0) or 0
        n_sets = row.get("n_sets", 0) or 0
        best_of = row.get("best_of", 3) or 3
        minutes = row.get("minutes")

        tiebreak_sets, tb_won, tb_lost = PlayerStatsEngine._tiebreak_counts(
            str(row.get("score", "")), is_winner)
        # 3rd set in best-of-3, 5th in best-of-5
        deciding_set = (n_sets == best_of) if n_sets > 0 and best_of > 0 else False

        return {
            "won": is_winner,
            "surface": row.get("surface"),
            "date": row.get("tourney_date"),
            "tourney_level": row.get("tourney_level"),
            "n_sets": n_sets,
            "total_games": total_games,
            "game_diff": game_diff if is_winner else -game_diff,
            "minutes": minutes if not pd.isna(minutes) else None,
            "tiebreak_sets": tiebreak_sets,
            "tb_won": tb_won,
            "tb_lost": tb_lost,
            "went_to_deciding_set": deciding_set,
            "deciding_set_won": deciding_set and is_winner,
            "opp_is_lefty": row.get(f"{opp_prefix}hand") == "L",
            "SvGms": row.get(f"{prefix}SvGms"),
            # Serve stats
            "svpt": row.get(f"{prefix}svpt"),
            "1stIn": row.get(f"{prefix}1stIn"),
            "1stWon": row.get(f"{prefix}1stWon"),
            "2ndWon": row.get(f"{prefix}2ndWon"),
            "ace": row.get(f"{prefix}ace"),
            "df": row.get(f"{prefix}df"),
            "bpSaved": row.get(f"{prefix}bpSaved"),
            "bpFaced": row.get(f"{prefix}bpFaced"),
            # Return stats (Opponent's serve stats)
            "opp_svpt": row.get(f"{opp_prefix}svpt"),
            "opp_1stWon": row.get(f"{opp_prefix}1stWon"),
            "opp_2ndWon": row.get(f"{opp_prefix}2ndWon"),
            "opp_bpFaced": row.get(f"{opp_prefix}bpFaced"),
            "opp_bpSaved": row.get(f"{opp_prefix}bpSaved"),
            "opp_SvGms": row.get(f"{opp_prefix}SvGms"),
        }

    def _store_match(self, player_id, surface, match_record):
        self.player_matches.setdefault(player_id, []).append(match_record)
        if surface:
            by_surface = self.player_surface_matches.setdefault(player_id, {})
            by_surface.setdefault(surface, []).append(match_record)

    def _record_h2h(self, row, player_id, opponent_id, is_winner):
        """Both perspectives: overall tally, dated meeting log and surface tally."""
        h2h_key = (player_id, opponent_id)
        opp_key = (opponent_id, player_id)
        self.h2h_records.setdefault(h2h_key, {"wins": 0, "losses": 0})
        self.h2h_records.setdefault(opp_key, {"wins": 0, "losses": 0})

        match_date = row.get("tourney_date")
        self.h2h_history[h2h_key].append((match_date, 1.0 if is_winner else 0.0))
        self.h2h_history[opp_key].append((match_date, 0.0 if is_winner else 1.0))

        if is_winner:
            self.h2h_records[h2h_key]["wins"] += 1
            self.h2h_records[opp_key]["losses"] += 1
        else:
            self.h2h_records[h2h_key]["losses"] += 1
            self.h2h_records[opp_key]["wins"] += 1

        # surface H2H is only credited from the winner's call
        surface = row.get("surface")
        if surface and is_winner:
            surf_key = (player_id, opponent_id, surface)
            opp_surf_key = (opponent_id, player_id, surface)
            self.h2h_records.setdefault(surf_key, {"wins": 0, "losses": 0})["wins"] += 1
            self.h2h_records.setdefault(opp_surf_key, {"wins": 0, "losses": 0})["losses"] += 1

    def record_match(self, row, is_winner=True):
        """
        Record a match result for a player (after features have been extracted).

        Args:
            row: DataFrame row with match data
            is_winner: Whether this player won
        """
        player_id = row.get("winner_id") if is_winner else row.get("loser_id")
        opponent_id = row.get("loser_id") if is_winner else row.get("winner_id")

        match_record = self._match_record(row, is_winner)
        self._store_match(player_id, row.get("surface"), match_record)
        self._record_h2h(row, player_id, opponent_id, is_winner)


def build_match_features(matches_df):
    """
    Build all features for every match in the dataset.
    Processes matches chronologically to avoid data leakage.

    Args:
        matches_df: Cleaned, chronologically sorted DataFrame

    Returns:
        DataFrame with feature columns added for both players
    """
    print("  ⏳ Calcolo feature giocatori...")

    engine = PlayerStatsEngine()
    feature_rows = []

    for row in matches_df.to_dict('records'):
        winner_id = row.get("winner_id")
        loser_id = row.get("loser_id")
        surface = row.get("surface", "Hard")
        match_date = row.get("tourney_date")

        if pd.isna(winner_id) or pd.isna(loser_id):
            feature_rows.append({})
            continue

        # Get PRE-MATCH features for both players
        w_feats = engine.get_player_features(winner_id, surface, loser_id, match_date)
        l_feats = engine.get_player_features(loser_id, surface, winner_id, match_date)

        # Prefix with p1_ (winner) and p2_ (loser)
        combined = {}
        for k, v in w_feats.items():
            combined[f"w_{k}"] = v
        for k, v in l_feats.items():
            combined[f"l_{k}"] = v

        feature_rows.append(combined)

        # Record match results (AFTER feature extraction)
        engine.record_match(row, is_winner=True)
        engine.record_match(row, is_winner=False)

    features_df = pd.DataFrame(feature_rows)
    result = pd.concat([matches_df.reset_index(drop=True), features_df], axis=1)

    print(f"  ✓ Feature calcolate: {len(features_df.columns)} colonne per {len(result):,} partite")
    return result
