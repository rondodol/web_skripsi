import pandas as pd
import numpy as np
import re
import os
import pickle
import warnings
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from main.models import Game  

warnings.filterwarnings('ignore')
ASSET_PATH = os.path.join(os.path.dirname(__file__), 'assets')

class GameRecommender:
    def __init__(self):
        print("Memuat dan memproses aset model rekomendasi...")
        self.df_games = None
        self.sbert_embeddings = None
        self.cos_sim_matrix = None
        self.cf_preds = None
        self.game_id_to_idx = None
        self._load_assets()
        print("Aset berhasil dimuat. Recommender siap digunakan.")

    def _load_assets(self):
        self.df_games = pd.read_pickle(os.path.join(ASSET_PATH, 'games_df.pkl'))
        self.sbert_embeddings = np.load(os.path.join(ASSET_PATH, 'sbert_embeddings.npy'))
        self.cos_sim_matrix = np.load(os.path.join(ASSET_PATH, 'cos_sim_matrix.npy'))
        with open(os.path.join(ASSET_PATH, 'cf_preds.pkl'), 'rb') as f:
            raw_preds = pickle.load(f)
        self.cf_preds = {
            (int(uid), int(iid)): float(score)
            for (uid, iid), score in raw_preds.items()
        }
        with open(os.path.join(ASSET_PATH, 'game_id_to_index.pkl'), 'rb') as f:
            self.game_id_to_idx = pickle.load(f)

    def _normalize_platform_input(self, input_platform):
        platform_map = {
            'ps5': 'playstation 5',
            'ps4': 'playstation 4',
            'ps3': 'playstation 3',
            'psvita': 'ps vita',
            'vita': 'ps vita',
            'ps': 'playstation',
            'xone': 'xbox one',
            'xbox360': 'xbox 360',
            'x360': 'xbox 360',
            'xsx': 'xbox series x',
            'xss': 'xbox series s/x',
            'switch': 'nintendo switch',
            'ns': 'nintendo switch',
            'nds': 'nintendo ds',
            '3ds': 'nintendo 3ds',
            'pc': 'pc',
            'mac': 'macos',
            'linux': 'linux',
            'ios': 'ios',
            'iphone': 'ios (iphone/ipad)',
            'android': 'android',
            'quest': 'meta quest',
        }

        key = input_platform.strip().lower().replace(' ', '')
        return platform_map.get(key, input_platform.strip().lower())


    # === FITUR 1: Cari Rekomendasi (Pure CBF)
    def search_recommendations(self, game_name=None, genre=None, platform=None, top_n=10):
        df = self.df_games.copy()

        def clean_text(text):
            return re.sub(r'[^a-z0-9 ]', '', str(text).lower())

        # === Normalisasi nama game ===
        df['name_clean'] = df['name'].astype(str).apply(clean_text)
        exclude_ids = set()

        # === Filter berdasarkan nama ===
        if game_name:
            game_name_clean = clean_text(game_name)
            df_name_match = df[df['name_clean'].str.contains(game_name_clean)]
            df = df_name_match.copy()
            # Hanya exclude game jika nama persis
            exact_match = df[df['name_clean'] == game_name_clean]
            exclude_ids = set(exact_match['game_id'].tolist())

        # === Filter genre ===
        if genre:
            df = df[df['genres'].str.contains(genre, case=False, na=False)]

        # === Filter platform ===
        if platform:
            normalized = self._normalize_platform_input(platform)
            df = df[df['platforms'].str.contains(normalized, case=False, na=False)]

        # === Fallback kalau hasil kosong ===
        if df.empty and (game_name or genre or platform):
            df = self.df_games.copy()

        if df.empty:
            return df.head(0)

        # === Cek vektor game yang valid ===
        query_vectors = [self._get_game_vector(gid) for gid in df['game_id'] if gid in self.game_id_to_idx]
        if not query_vectors:
            return df.head(0)

        # === Hitung similarity dan ambil top_n ===
        avg_vector = np.mean(query_vectors, axis=0).reshape(1, -1)
        sims = cosine_similarity(avg_vector, self.sbert_embeddings)[0]
        sim_series = pd.Series(sims, index=self.df_games['game_id'])
        sim_series = sim_series[~sim_series.index.isin(exclude_ids)]  # Jangan rekomendasiin yang persis
        top_ids = sim_series.sort_values(ascending=False).head(top_n).index.tolist()

        return self.df_games[self.df_games['game_id'].isin(top_ids)]

    # === FITUR 2: Game Serupa (Pure CBF)
    def get_similar_games(self, game_id, top_n=5):
        if game_id not in self.game_id_to_idx:
            print(f"[SIMILAR] Game ID {game_id} tidak ditemukan di indeks.")
            return Game.objects.none()
    
        idx = self.game_id_to_idx[game_id]
        sims = self.cos_sim_matrix[idx]
        sim_series = pd.Series(sims, index=self.df_games['game_id']).drop(game_id, errors='ignore')
        top_ids = sim_series.sort_values(ascending=False).head(top_n).index.tolist()

        print("[SIMILAR] Top rekomendasi untuk game:", game_id, "->", top_ids)
        return Game.objects.filter(game_id__in=top_ids)

    # === FITUR 3: Mungkin Anda Menyukai (Hybrid)
    def get_hybrid_recommendations(self, user_genres, user_platforms, user_id=None, top_n=10, alpha=0.5):
        df = self.df_games.copy()

        # Step 1: Ambil preferensi
        genre_list = [g.strip().lower() for g in user_genres.split(',') if g.strip()]
        platform_list = [self._normalize_platform_input(p) for p in user_platforms.split(',') if p.strip()]

        # Step 2: Filter game yang match preferensi
        def match_genre(row): return any(g in row.lower() for g in genre_list)
        def match_platform(row): return any(p in row.lower() for p in platform_list)

        df_pref = df[
            df['genres'].apply(lambda x: match_genre(x)) |
            df['platforms'].apply(lambda x: match_platform(x))
        ]

        # Step 3: Buat vector user dari hasil preferensi (walaupun cuma 1-3 game)
        vectors = [self._get_game_vector(gid) for gid in df_pref['game_id'] if gid in self.game_id_to_idx]
        if not vectors:
            return df.head(0)  # kosong total

        avg_vector = np.mean(vectors, axis=0).reshape(1, -1)
        cosine_scores = cosine_similarity(avg_vector, self.sbert_embeddings)[0]
        cbf_series = pd.Series(cosine_scores, index=self.df_games['game_id'])

        # Step 4: CF score
        cf_series = pd.Series({gid: self.cf_preds.get((user_id, gid), 0) / 5.0 for gid in self.df_games['game_id']})

        # Step 5: Hybrid score
        hybrid_series = alpha * cbf_series + (1 - alpha) * cf_series
        hybrid_series = hybrid_series.sort_values(ascending=False)

        # Step 6: Prioritaskan hasil yang match preferensi user (genre/platform)
        hybrid_ids_pref = [gid for gid in hybrid_series.index if gid in df_pref['game_id'].values]
        hybrid_ids_other = [gid for gid in hybrid_series.index if gid not in hybrid_ids_pref]

        # Gabungkan, ambil top_n total
        top_ids = (hybrid_ids_pref + hybrid_ids_other)[:top_n]
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
            return self.sbert_embeddings[self.game_id_to_idx[game_id]]
        return np.zeros(self.sbert_embeddings.shape[1])
