"""
Tennis Prediction Model - Player Statistics & Feature Engineering
Computes rolling stats, head-to-head records, form, fatigue, and all match features.
"""

import pandas as pd
import numpy as np
from collections import defaultdict


def _num(v):
    """NaN/None-safe numeric coercion. CRITICAL: `np.nan or 0` returns np.nan
    (NaN is truthy in Python), so the old `m.get(k, 0) or 0` pattern let a SINGLE
    stat-less match in a rolling window poison the whole sum -> the entire _50
    serve/return aggregate became NaN. With ~6% of matches lacking serve stats,
    a 50-match window hit a NaN ~95% of the time. `v != v` is True only for NaN."""
    return 0 if v is None or v != v else v


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
        total_1stIn = sum(_num(m.get(f"{prefix}1stIn")) for m in matches)
        total_1stWon = sum(_num(m.get(f"{prefix}1stWon")) for m in matches)
        total_2ndWon = sum(_num(m.get(f"{prefix}2ndWon")) for m in matches)
        total_ace = sum(_num(m.get(f"{prefix}ace")) for m in matches)
        total_df = sum(_num(m.get(f"{prefix}df")) for m in matches)
        total_bpSaved = sum(_num(m.get(f"{prefix}bpSaved")) for m in matches)
        total_bpFaced = sum(_num(m.get(f"{prefix}bpFaced")) for m in matches)

        stats["pct_1st_in"] = total_1stIn / total_svpt if total_svpt > 0 else np.nan
        stats["pct_1st_won"] = total_1stWon / total_1stIn if total_1stIn > 0 else np.nan
        svpt_2nd = total_svpt - total_1stIn
        stats["pct_2nd_won"] = total_2ndWon / svpt_2nd if svpt_2nd > 0 else np.nan
        stats["ace_rate"] = total_ace / total_svpt if total_svpt > 0 else np.nan
        stats["df_rate"] = total_df / total_svpt if total_svpt > 0 else np.nan
        stats["bp_save_pct"] = total_bpSaved / total_bpFaced if total_bpFaced > 0 else np.nan

        return stats

    def _return_stats(self, matches):
        """Calculate return statistics from a list of matches."""
        if not matches:
            return {}

        stats = {}
        total_opp_svpt = sum(_num(m.get("opp_svpt")) for m in matches)
        total_opp_1stWon = sum(_num(m.get("opp_1stWon")) for m in matches)
        total_opp_2ndWon = sum(_num(m.get("opp_2ndWon")) for m in matches)
        total_opp_bpFaced = sum(_num(m.get("opp_bpFaced")) for m in matches)
        total_opp_bpSaved = sum(_num(m.get("opp_bpSaved")) for m in matches)
        total_opp_SvGms = sum(_num(m.get("opp_SvGms")) for m in matches)
        
        total_opp_pts_won = total_opp_1stWon + total_opp_2ndWon
        stats["return_pts_win_pct"] = (total_opp_svpt - total_opp_pts_won) / total_opp_svpt if total_opp_svpt > 0 else np.nan
        
        bp_converted = total_opp_bpFaced - total_opp_bpSaved
        stats["bp_convert_pct"] = bp_converted / total_opp_bpFaced if total_opp_bpFaced > 0 else np.nan
        stats["break_rate"] = bp_converted / total_opp_SvGms if total_opp_SvGms > 0 else np.nan

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

    def _totals_stats(self, matches):
        """Calculate totals-oriented stats: avg games, sets, duration, closeness."""
        if not matches:
            return {}

        stats = {}
        games_list = [m.get("total_games") for m in matches if m.get("total_games") and m["total_games"] > 0]
        sets_list = [m.get("n_sets") for m in matches if m.get("n_sets") and m["n_sets"] > 0]
        margin_list = [abs(m.get("game_diff", 0) or 0) for m in matches if m.get("total_games") and m["total_games"] > 0]
        minutes_list = [m.get("minutes") for m in matches if m.get("minutes") and m["minutes"] > 0]
        
        tb_won = sum(m.get("tb_won", 0) or 0 for m in matches)
        tb_lost = sum(m.get("tb_lost", 0) or 0 for m in matches)
        tb_sets = tb_won + tb_lost
        
        total_sets = sum(m.get("n_sets", 0) or 0 for m in matches)
        
        deciding_sets = sum(1 for m in matches if m.get("went_to_deciding_set"))
        deciding_sets_won = sum(1 for m in matches if m.get("deciding_set_won"))
        
        matches_vs_lefty = sum(1 for m in matches if m.get("opp_is_lefty"))
        wins_vs_lefty = sum(1 for m in matches if m.get("opp_is_lefty") and m.get("won"))

        stats["avg_total_games"] = np.mean(games_list) if games_list else np.nan
        stats["avg_game_margin"] = np.mean(margin_list) if margin_list else np.nan
        stats["avg_sets_per_match"] = np.mean(sets_list) if sets_list else np.nan
        stats["avg_minutes"] = np.mean(minutes_list) if minutes_list else np.nan

        gps = [
            m["total_games"] / m["n_sets"]
            for m in matches
            if m.get("total_games") and m["total_games"] > 0
            and m.get("n_sets") and m["n_sets"] > 0
        ]
        stats["avg_games_per_set"] = np.mean(gps) if gps else np.nan

        stats["tiebreak_rate"] = tb_sets / total_sets if total_sets > 0 else np.nan
        stats["tiebreak_win_pct"] = tb_won / tb_sets if tb_sets > 0 else np.nan
        
        stats["deciding_set_pct"] = deciding_sets / len(matches) if matches else np.nan
        stats["deciding_set_win_pct"] = deciding_sets_won / deciding_sets if deciding_sets > 0 else np.nan
        
        stats["vs_lefty_win_pct"] = wins_vs_lefty / matches_vs_lefty if matches_vs_lefty > 0 else np.nan

        # Hold percentage: service games won / total service games
        sv_gms = sum(_num(m.get("SvGms")) for m in matches)
        bp_faced = sum(_num(m.get("bpFaced")) for m in matches)
        bp_saved = sum(_num(m.get("bpSaved")) for m in matches)
        breaks_against = bp_faced - bp_saved
        holds = sv_gms - breaks_against if sv_gms > 0 else 0
        stats["hold_pct"] = holds / sv_gms if sv_gms > 0 else np.nan

        return stats

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
        minutes_14d = 0
        decay_minutes_14d = 0.0
        for m in reversed(matches):
            m_date = m.get("date")
            if m_date and not pd.isna(m_date):
                delta = (current_date - m_date).days
                if delta <= 14:
                    mn = m.get("minutes")
                    if mn and not pd.isna(mn):
                        minutes_14d += mn
                        # Decay: half-life of 4 days. Match 1 day ago = 84% weight. Match 7 days ago = 30% weight.
                        decay_minutes_14d += mn * (0.5 ** (delta / 4.0))
                if delta > 14:
                    break

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

        # Head-to-head
        if opponent_id:
            h2h_key = (player_id, opponent_id)
            h2h = self.h2h_records.get(h2h_key, {"wins": 0, "losses": 0})
            features["h2h_wins"] = h2h["wins"]
            features["h2h_losses"] = h2h["losses"]
            total_h2h = h2h["wins"] + h2h["losses"]
            features["h2h_win_rate"] = h2h["wins"] / total_h2h if total_h2h > 0 else 0.5

            # H2H on surface
            h2h_surface_key = (player_id, opponent_id, surface)
            h2h_s = self.h2h_records.get(h2h_surface_key, {"wins": 0, "losses": 0})
            total_h2h_s = h2h_s["wins"] + h2h_s["losses"]
            features["h2h_surface_win_rate"] = h2h_s["wins"] / total_h2h_s if total_h2h_s > 0 else 0.5

            # Recency-weighted H2H: only meetings within the last 2 years.
            hist = self.h2h_history.get((player_id, opponent_id), [])
            recent_meet = [
                won for (d, won) in hist
                if d is not None and not pd.isna(d)
                and (match_date is None or (match_date - d).days <= 730)
            ]
            features["h2h_recent_win_rate"] = (
                sum(recent_meet) / len(recent_meet) if recent_meet else 0.5
            )
            features["h2h_recent_n"] = float(len(recent_meet))

        # Momentum / recent form
        features.update(self._form_features(recent_10))

        # Fatigue
        fatigue = self._fatigue_features(matches, match_date)
        features.update(fatigue)

        return features

    def record_match(self, row, is_winner=True):
        """
        Record a match result for a player (after features have been extracted).

        Args:
            row: DataFrame row with match data
            is_winner: Whether this player won
        """
        player_id = row.get("winner_id") if is_winner else row.get("loser_id")
        opponent_id = row.get("loser_id") if is_winner else row.get("winner_id")

        # Prefix for stats columns
        prefix = "w_" if is_winner else "l_"
        opp_prefix = "l_" if is_winner else "w_"

        # Parse score-level data for totals features
        score = str(row.get("score", ""))
        total_games = row.get("total_games", 0) or 0
        game_diff = row.get("game_diff", 0) or 0
        n_sets = row.get("n_sets", 0) or 0
        best_of = row.get("best_of", 3) or 3
        minutes = row.get("minutes")

        # Count tiebreak sets from score string (e.g., "7-6(5)" pattern)
        # Score is always from the match winner's perspective in raw data
        import re
        if not isinstance(score, str):
            score = ""
        tb_won_match_winner = len(re.findall(r'7-6', score))
        tb_lost_match_winner = len(re.findall(r'6-7', score))
        tiebreak_sets = tb_won_match_winner + tb_lost_match_winner
        
        tb_won = tb_won_match_winner if is_winner else tb_lost_match_winner
        tb_lost = tb_lost_match_winner if is_winner else tb_won_match_winner
        
        # Went to deciding set? (3rd set in best-of-3, 5th in best-of-5)
        deciding_set = (n_sets == best_of) if n_sets > 0 and best_of > 0 else False

        match_record = {
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

        if player_id not in self.player_matches:
            self.player_matches[player_id] = []
        self.player_matches[player_id].append(match_record)

        surface = row.get("surface")
        if surface:
            if player_id not in self.player_surface_matches:
                self.player_surface_matches[player_id] = {}
            if surface not in self.player_surface_matches[player_id]:
                self.player_surface_matches[player_id][surface] = []
            self.player_surface_matches[player_id][surface].append(match_record)

        # Update H2H
        h2h_key = (player_id, opponent_id)
        opp_key = (opponent_id, player_id)
        
        if h2h_key not in self.h2h_records: self.h2h_records[h2h_key] = {"wins": 0, "losses": 0}
        if opp_key not in self.h2h_records: self.h2h_records[opp_key] = {"wins": 0, "losses": 0}

        # Dated meeting log for recency-weighted H2H (both perspectives).
        match_date = row.get("tourney_date")
        self.h2h_history[h2h_key].append((match_date, 1.0 if is_winner else 0.0))
        self.h2h_history[opp_key].append((match_date, 0.0 if is_winner else 1.0))

        if is_winner:
            self.h2h_records[h2h_key]["wins"] += 1
            self.h2h_records[opp_key]["losses"] += 1
        else:
            self.h2h_records[h2h_key]["losses"] += 1
            self.h2h_records[opp_key]["wins"] += 1

        # Surface H2H
        surface = row.get("surface")
        if surface:
            h2h_surf = (player_id, opponent_id, surface)
            if is_winner:
                if h2h_surf not in self.h2h_records:
                    self.h2h_records[h2h_surf] = {"wins": 0, "losses": 0}
                self.h2h_records[h2h_surf]["wins"] += 1
                opp_surf = (opponent_id, player_id, surface)
                if opp_surf not in self.h2h_records:
                    self.h2h_records[opp_surf] = {"wins": 0, "losses": 0}
                self.h2h_records[opp_surf]["losses"] += 1


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
