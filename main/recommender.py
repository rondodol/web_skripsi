import pandas as pd
import numpy as np
import os
import pickle
import warnings
from sklearn.metrics.pairwise import cosine_similarity
from main.models import Game  # Sesuaikan jika kamu deploy atau struktur berubah

warnings.filterwarnings('ignore')

ASSET_PATH = os.path.join(os.path.dirname(__file__), 'assets')

class GameRecommender:
    def __init__(self):
        print("Memuat dan memproses aset model rekomendasi...")
        self.df_games = None
        self.cos_sim_matrix = None
        self.cf_preds = None
        self.game_id_to_idx = None
        self._load_assets()
        print("Aset berhasil dimuat. Recommender siap digunakan.")

    def _load_assets(self):
        self.df_games = pd.read_pickle(os.path.join(ASSET_PATH, 'games_df.pkl'))
        self.cos_sim_matrix = np.load(os.path.join(ASSET_PATH, 'cos_sim_matrix.npy'))
        with open(os.path.join(ASSET_PATH, 'cf_preds.pkl'), 'rb') as f:
            self.cf_preds = pickle.load(f)
        with open(os.path.join(ASSET_PATH, 'game_id_to_index.pkl'), 'rb') as f:
            self.game_id_to_idx = pickle.load(f)

    def _normalize_platform_input(self, input_platform):
        platform_map = {
            'ps5': 'playstation 5', 'ps4': 'playstation 4', 'ps3': 'playstation 3',
            'ps2': 'playstation 2', 'ps': 'playstation', 'xbox': 'xbox',
            'xone': 'xbox one', 'x360': 'xbox 360', 'pc': 'pc',
            'ns': 'nintendo switch', 'switch': 'nintendo switch',
            'nintendo': 'nintendo', 'wii': 'wii', 'ds': 'nintendo ds',
            'mobile': 'ios', 'android': 'android'
        }
        return platform_map.get(input_platform.strip().lower(), input_platform)

    # === FITUR 1: Cari Rekomendasi (Pure CBF)
    def search_recommendations(self, game_name=None, genre=None, platform=None, top_n=10):
        df = self.df_games.copy()
        if game_name:
            df = df[df['name'].str.contains(game_name, case=False, na=False)]
        if genre:
            df = df[df['genres'].str.contains(genre, case=False, na=False)]
        if platform:
            norm_platform = self._normalize_platform_input(platform)
            df = df[df['platforms'].str.contains(norm_platform, case=False, na=False)]
        if df.empty:
            return df.head(0)

        vectors = [self._get_game_vector(gid) for gid in df['game_id'] if gid in self.game_id_to_idx]
        if not vectors:
            return df.head(0)

        avg_vector = np.mean(vectors, axis=0).reshape(1, -1)
        sims = cosine_similarity(avg_vector, self.cos_sim_matrix)[0]
        sim_series = pd.Series(sims, index=self.df_games['game_id'])
        top_ids = sim_series.sort_values(ascending=False).head(top_n).index.tolist()
        return self.df_games[self.df_games['game_id'].isin(top_ids)]

    # === FITUR 2: Game Serupa (Pure CBF)
    def get_similar_games(self, game_id, top_n=5):
        if game_id not in self.game_id_to_idx:
            return Game.objects.none()
        idx = self.game_id_to_idx[game_id]
        sims = self.cos_sim_matrix[idx]
        sim_series = pd.Series(sims, index=self.df_games['game_id']).drop(game_id, errors='ignore')
        top_ids = sim_series.sort_values(ascending=False).head(top_n).index.tolist()
        return Game.objects.filter(game_id__in=top_ids)

    # === FITUR 3: Mungkin Anda Menyukai (Hybrid)
    def get_hybrid_recommendations(self, user_genres, user_platforms, user_id=None, top_n=10):
        alpha = 0.5  # SET FIXED ALPHA

        df = self.df_games.copy()
        if user_genres:
            df = df[df['genres'].str.contains(user_genres, case=False, na=False)]
        if user_platforms:
            normalized = self._normalize_platform_input(user_platforms)
            df = df[df['platforms'].str.contains(normalized, case=False, na=False)]
        if df.empty:
            return df.head(0)

        rated_game_ids = df['game_id'].tolist()
        scored = []
        for gid in self.df_games['game_id']:
            cf_score = self.cf_preds.get((user_id, gid), 0) / 5.0  # ganti dari "web_user"
            if gid not in self.game_id_to_idx:
                cbf_score = 0
            else:
                sims = [self.cos_sim_matrix[self.game_id_to_idx[gid]][self.game_id_to_idx[r]]
                        for r in rated_game_ids if r in self.game_id_to_idx]
                cbf_score = np.mean(sims) if sims else 0
            hybrid = alpha * cbf_score + (1 - alpha) * cf_score
            scored.append((gid, hybrid))

        top_ids = [gid for gid, _ in sorted(scored, key=lambda x: x[1], reverse=True)[:top_n]]
        return self.df_games[self.df_games['game_id'].isin(top_ids)]


    # === FITUR 4: User Lain Juga Menyukai (Pure CF)
    def get_cf_recommendations(self, user_id, top_n=10):
        scored = [(gid, score) for (uid, gid), score in self.cf_preds.items() if uid == user_id]
        if not scored:
            return self.df_games.head(0)
        top_ids = [gid for gid, _ in sorted(scored, key=lambda x: x[1], reverse=True)[:top_n]]
        return self.df_games[self.df_games['game_id'].isin(top_ids)]

    def _get_game_vector(self, game_id):
        if game_id in self.game_id_to_idx:
            return self.cos_sim_matrix[self.game_id_to_idx[game_id]]
        return np.zeros(self.cos_sim_matrix.shape[1])
