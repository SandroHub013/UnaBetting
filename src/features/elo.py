"""
Tennis Prediction Model - ELO Rating System
Implements global and surface-specific ELO ratings for tennis players.
"""

import pandas as pd
import numpy as np
import re
from collections import defaultdict

def parse_score_games(score):
    """Parse a tennis score string and return (winner_games, loser_games)."""
    if not isinstance(score, str) or "W/O" in score or "RET" in score or "DEF" in score:
        return 0, 0
    
    score_clean = re.sub(r'\(\d+\)', '', score) # Remove tiebreak points
    w_games, l_games = 0, 0
    sets = score_clean.split()
    for s in sets:
        parts = s.split('-')
        if len(parts) == 2:
            try:
                w_games += int(parts[0])
                l_games += int(parts[1])
            except ValueError:
                pass
    return w_games, l_games


class EloRating:
    """
    Dynamic ELO rating system for tennis, with surface-specific variants.

    Features:
    - Global ELO across all surfaces
    - Per-surface ELO (Hard, Clay, Grass)
    - Adjustable K-factor by tournament level
    - Time decay for inactive players
    - Indoor/Outdoor distinction (optional)
    """

    def __init__(
        self,
        k_factor=32,
        k_factor_grand_slam=48,
        k_factor_masters=40,
        initial_rating=1500,
        surface_weight=0.7,
    ):
        self.k_factor = k_factor
        self.k_factor_grand_slam = k_factor_grand_slam
        self.k_factor_masters = k_factor_masters
        self.initial_rating = initial_rating
        self.surface_weight = surface_weight

        # Ratings storage: {player_id: rating}
        self.global_ratings = {}
        self.surface_ratings = {
            "Hard": {},
            "Clay": {},
            "Grass": {},
            "Carpet": {},
        }
        
        # Style ELO ratings
        self.vs_server_ratings = {}
        self.vs_returner_ratings = {}
        
        # Player stats to classify style dynamically
        from collections import defaultdict
        self.player_stats = defaultdict(lambda: {"svpt": 0, "ace": 0, "ret_pt": 0, "ret_won": 0})

        # Match count per player (for adjusting K-factor for newcomers)
        self.match_count = {}
        self.surface_match_count = {
            s: {} for s in self.surface_ratings
        }

        # History for analysis
        self.history = []
        
        # Time Decay
        self.last_played_date = {}
        self.decay_rate_per_day = 0.05 / 365  # 5% decay per year

    def apply_time_decay(self, player_id, current_date):
        """Apply ELO decay towards the mean (1500) if inactive for >30 days."""
        if player_id not in self.last_played_date:
            return
        last_date = self.last_played_date[player_id]
        
        # Ensure we are comparing datetimes
        current_date = pd.to_datetime(current_date)
        last_date = pd.to_datetime(last_date)
        
        if pd.isna(last_date) or pd.isna(current_date):
            return
            
        days_since = (current_date - last_date).days
        if days_since > 30:
            decay_factor = 1.0 - min(1.0, self.decay_rate_per_day * days_since)
            diff = self.global_ratings.get(player_id, self.initial_rating) - self.initial_rating
            self.global_ratings[player_id] = self.initial_rating + diff * decay_factor
            
            for surface in self.surface_ratings:
                s_diff = self.surface_ratings[surface].get(player_id, self.initial_rating) - self.initial_rating
                self.surface_ratings[surface][player_id] = self.initial_rating + s_diff * decay_factor

    def _get_k_factor(self, tourney_level, player_id):
        """
        Get K-factor based on tournament level and player experience.
        New players get higher K-factor for faster convergence.
        """
        # Base K by tournament level
        if tourney_level == "G":
            base_k = self.k_factor_grand_slam
        elif tourney_level == "M":
            base_k = self.k_factor_masters
        else:
            base_k = self.k_factor

        # Newcomer boost (Young Talents / Breakout Players)
        # Higher K for their early career to let their ELO skyrocket if they win against veterans
        matches_played = self.match_count.get(player_id, 0)
        if matches_played < 10:
            return base_k * 2.5
        elif matches_played < 30:
            return base_k * 1.8
        elif matches_played < 50:
            return base_k * 1.3

        return base_k

    def expected_score(self, rating_a, rating_b):
        """Calculate expected score (win probability) for player A vs B."""
        return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))

    def get_combined_rating(self, player_id, surface):
        global_elo = self.global_ratings.get(player_id, self.initial_rating)

        if surface in self.surface_ratings:
            surface_elo = self.surface_ratings[surface].get(player_id, self.initial_rating)
            # Only use surface-specific if enough matches on that surface
            if self.surface_match_count[surface].get(player_id, 0) >= 5:
                return self.surface_weight * surface_elo + (1 - self.surface_weight) * global_elo
            else:
                return global_elo
        else:
            return global_elo

    def update(self, winner_id, loser_id, surface, tourney_level="A",
               tourney_date=None, match_id=None, score=None):
        """
        Update ELO ratings after a match result.

        Args:
            winner_id: ID of winning player
            loser_id: ID of losing player
            surface: Playing surface (Hard, Clay, Grass, Carpet)
            tourney_level: Tournament level (G, M, A, D, F)
            tourney_date: Match date (for history)
            match_id: Optional match identifier

        Returns:
            dict with pre-match ratings and probabilities
        """
        # Get pre-match ratings
        w_global = self.global_ratings.get(winner_id, self.initial_rating)
        l_global = self.global_ratings.get(loser_id, self.initial_rating)
        w_combined = self.get_combined_rating(winner_id, surface)
        l_combined = self.get_combined_rating(loser_id, surface)

        # Expected scores (using combined ratings for prediction)
        w_expected = self.expected_score(w_combined, l_combined)
        l_expected = 1.0 - w_expected

        # Margin of Victory multiplier
        mov_mult = 1.0
        if score:
            w_games, l_games = parse_score_games(score)
            games_diff = w_games - l_games
            total_games = w_games + l_games
            if total_games > 0 and games_diff > 0:
                mov_mult = 1.0 + 0.5 * (games_diff / total_games)

        # K-factors
        w_k = self._get_k_factor(tourney_level, winner_id) * mov_mult
        l_k = self._get_k_factor(tourney_level, loser_id) * mov_mult

        # Update global ratings
        w_expected_global = self.expected_score(w_global, l_global)
        l_expected_global = 1.0 - w_expected_global
        self.global_ratings[winner_id] = w_global + w_k * (1.0 - w_expected_global)
        self.global_ratings[loser_id] = l_global + l_k * (0.0 - l_expected_global)

        # Update surface-specific ratings
        if surface in self.surface_ratings:
            w_surface = self.surface_ratings[surface].get(winner_id, self.initial_rating)
            l_surface = self.surface_ratings[surface].get(loser_id, self.initial_rating)
            w_exp_surf = self.expected_score(w_surface, l_surface)
            l_exp_surf = 1.0 - w_exp_surf
            self.surface_ratings[surface][winner_id] = w_surface + w_k * (1.0 - w_exp_surf)
            self.surface_ratings[surface][loser_id] = l_surface + l_k * (0.0 - l_exp_surf)
            self.surface_match_count[surface][winner_id] = self.surface_match_count[surface].get(winner_id, 0) + 1
            self.surface_match_count[surface][loser_id] = self.surface_match_count[surface].get(loser_id, 0) + 1

        # Update match counts
        self.match_count[winner_id] = self.match_count.get(winner_id, 0) + 1
        self.match_count[loser_id] = self.match_count.get(loser_id, 0) + 1

        # Record for history
        result = {
            "match_id": match_id,
            "tourney_date": tourney_date,
            "surface": surface,
            "winner_id": winner_id,
            "loser_id": loser_id,
            "w_elo_before": w_global,
            "l_elo_before": l_global,
            "w_elo_after": self.global_ratings[winner_id],
            "l_elo_after": self.global_ratings[loser_id],
            "w_surface_elo_before": w_combined,
            "l_surface_elo_before": l_combined,
            "w_win_prob": w_expected,
            "l_win_prob": l_expected,
        }
        self.history.append(result)

        if tourney_date and not pd.isna(tourney_date):
            self.last_played_date[winner_id] = tourney_date
            self.last_played_date[loser_id] = tourney_date

        return result

    def process_matches(self, matches_df):
        """
        Process a chronologically sorted DataFrame of matches.
        Adds ELO columns to each row BEFORE the match is played (pre-match ELO).

        Args:
            matches_df: DataFrame with columns:
                winner_id, loser_id, surface, tourney_level, tourney_date

        Returns:
            DataFrame with added ELO columns
        """
        print("  ⏳ Calcolo ELO ratings...")

        elo_data = []

        for row in matches_df.to_dict('records'):
            winner_id = row.get("winner_id")
            loser_id = row.get("loser_id")
            surface = row.get("surface", "Hard")
            tourney_level = row.get("tourney_level", "A")
            tourney_date = row.get("tourney_date")
            score = row.get("score")

            if pd.isna(winner_id) or pd.isna(loser_id):
                elo_data.append({
                    "w_elo": np.nan, "l_elo": np.nan,
                    "w_surface_elo": np.nan, "l_surface_elo": np.nan,
                    "elo_win_prob": np.nan, "elo_surface_win_prob": np.nan,
                    "w_vs_server_elo": np.nan, "l_vs_server_elo": np.nan,
                    "w_vs_returner_elo": np.nan, "l_vs_returner_elo": np.nan
                })
                continue

            # Apply Time Decay BEFORE getting ratings
            if pd.notna(tourney_date):
                self.apply_time_decay(winner_id, tourney_date)
                self.apply_time_decay(loser_id, tourney_date)

            # Classify opponents based on historical stats
            w_stats = self.player_stats[winner_id]
            l_stats = self.player_stats[loser_id]
            
            def is_server(stats):
                return (stats["ace"] / stats["svpt"]) > 0.08 if stats["svpt"] > 200 else False
            
            def is_returner(stats):
                return (stats["ret_won"] / stats["ret_pt"]) > 0.38 if stats["ret_pt"] > 200 else False

            w_is_srv = is_server(w_stats)
            w_is_ret = is_returner(w_stats)
            l_is_srv = is_server(l_stats)
            l_is_ret = is_returner(l_stats)

            # Get PRE-MATCH ratings
            w_elo = self.global_ratings.get(winner_id, self.initial_rating)
            l_elo = self.global_ratings.get(loser_id, self.initial_rating)
            w_surface_elo = self.get_combined_rating(winner_id, surface)
            l_surface_elo = self.get_combined_rating(loser_id, surface)
            win_prob = self.expected_score(w_surface_elo, l_surface_elo)
            
            # Pure surface ELO probability
            w_pure_surface = self.surface_ratings.get(surface, {}).get(winner_id, self.initial_rating) if surface in self.surface_ratings else self.initial_rating
            l_pure_surface = self.surface_ratings.get(surface, {}).get(loser_id, self.initial_rating) if surface in self.surface_ratings else self.initial_rating
            surface_win_prob = self.expected_score(w_pure_surface, l_pure_surface)

            # Get PRE-MATCH Style ratings
            w_vs_srv_elo = self.vs_server_ratings.get(winner_id, self.initial_rating) if l_is_srv else np.nan
            l_vs_srv_elo = self.vs_server_ratings.get(loser_id, self.initial_rating) if w_is_srv else np.nan
            
            w_vs_ret_elo = self.vs_returner_ratings.get(winner_id, self.initial_rating) if l_is_ret else np.nan
            l_vs_ret_elo = self.vs_returner_ratings.get(loser_id, self.initial_rating) if w_is_ret else np.nan

            elo_data.append({
                "w_elo": w_elo, "l_elo": l_elo,
                "w_surface_elo": w_surface_elo, "l_surface_elo": l_surface_elo,
                "elo_win_prob": win_prob, "elo_surface_win_prob": surface_win_prob,
                "w_vs_server_elo": w_vs_srv_elo, "l_vs_server_elo": l_vs_srv_elo,
                "w_vs_returner_elo": w_vs_ret_elo, "l_vs_returner_elo": l_vs_ret_elo
            })

            # UPDATE ratings (global and surface)
            self.update(winner_id, loser_id, surface, tourney_level, tourney_date, score=score)
            
            # Update Style ELO
            mov_mult = 1.0
            if score:
                w_g, l_g = parse_score_games(score)
                if w_g + l_g > 0 and (w_g - l_g) > 0:
                    mov_mult = 1.0 + 0.5 * ((w_g - l_g) / (w_g + l_g))
            
            w_k = self._get_k_factor(tourney_level, winner_id) * mov_mult
            l_k = self._get_k_factor(tourney_level, loser_id) * mov_mult
            
            # If opponent is a server, update player's vs_server rating against opponent's combined rating
            if l_is_srv:
                base_w = self.vs_server_ratings.get(winner_id, self.initial_rating)
                w_exp = self.expected_score(base_w, l_surface_elo)
                self.vs_server_ratings[winner_id] = base_w + w_k * (1.0 - w_exp)
            if w_is_srv:
                base_l = self.vs_server_ratings.get(loser_id, self.initial_rating)
                l_exp = self.expected_score(base_l, w_surface_elo)
                self.vs_server_ratings[loser_id] = base_l + l_k * (0.0 - l_exp)
                
            # If opponent is a returner
            if l_is_ret:
                base_w = self.vs_returner_ratings.get(winner_id, self.initial_rating)
                w_exp = self.expected_score(base_w, l_surface_elo)
                self.vs_returner_ratings[winner_id] = base_w + w_k * (1.0 - w_exp)
            if w_is_ret:
                base_l = self.vs_returner_ratings.get(loser_id, self.initial_rating)
                l_exp = self.expected_score(base_l, w_surface_elo)
                self.vs_returner_ratings[loser_id] = base_l + l_k * (0.0 - l_exp)
                
            # Update Player Stats for future matches
            w_svpt = row.get("w_svpt")
            w_ace = row.get("w_ace")
            l_svpt = row.get("l_svpt")
            l_ace = row.get("l_ace")
            l_1st = row.get("l_1stWon", 0)
            l_2nd = row.get("l_2ndWon", 0)
            w_1st = row.get("w_1stWon", 0)
            w_2nd = row.get("w_2ndWon", 0)
            
            if pd.notna(w_svpt) and pd.notna(w_ace):
                self.player_stats[winner_id]["svpt"] += w_svpt
                self.player_stats[winner_id]["ace"] += w_ace
                # Loser return points
                self.player_stats[loser_id]["ret_pt"] += w_svpt
                self.player_stats[loser_id]["ret_won"] += (w_svpt - w_1st - w_2nd)
                
            if pd.notna(l_svpt) and pd.notna(l_ace):
                self.player_stats[loser_id]["svpt"] += l_svpt
                self.player_stats[loser_id]["ace"] += l_ace
                # Winner return points
                self.player_stats[winner_id]["ret_pt"] += l_svpt
                self.player_stats[winner_id]["ret_won"] += (l_svpt - l_1st - l_2nd)

        elo_df = pd.DataFrame(elo_data)
        result = pd.concat([matches_df.reset_index(drop=True), elo_df], axis=1)

        print(f"  ✓ ELO calcolato per {len(result):,} partite")
        print(f"  📊 Top 10 giocatori (ELO globale):")

        top_players = sorted(
            self.global_ratings.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]
        for rank, (pid, elo) in enumerate(top_players, 1):
            print(f"    {rank}. ID {pid}: {elo:.0f}")

        return result

    def get_rating_history_df(self):
        """Return the full rating history as a DataFrame."""
        return pd.DataFrame(self.history)

    def get_current_ratings_df(self):
        """Return current ratings for all players."""
        data = []
        for pid in self.global_ratings:
            row = {
                "player_id": pid,
                "elo_global": self.global_ratings[pid],
                "matches_played": self.match_count[pid],
            }
            for surface in self.surface_ratings:
                row[f"elo_{surface.lower()}"] = self.surface_ratings[surface][pid]
                row[f"matches_{surface.lower()}"] = self.surface_match_count[surface][pid]
            data.append(row)

        df = pd.DataFrame(data)
        return df.sort_values("elo_global", ascending=False).reset_index(drop=True)
