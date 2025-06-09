import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import os
import warnings
from main.models import Game
warnings.filterwarnings('ignore')
ASSET_PATH = os.path.join(os.path.dirname(__file__), 'assets')

class GameRecommender:
    def __init__(self):
        print("Memuat dan memproses aset model rekomendasi...")
        self.df_games = None
        self.sbert_model = None
        self.sbert_embeddings = None
        self.training_user_profiles = {}
        self.cf_recs_map = {}
        self.game_id_to_idx = {}
        self.popular_games_df = None
        self._load_and_preprocess_assets()
        print("Aset berhasil dimuat. Recommender siap digunakan.")

    def _load_and_preprocess_assets(self):
        try:
            # Muat aset dasar
            self.df_games = pd.read_pickle(os.path.join(ASSET_PATH, 'games_df.pkl'))
            self.game_id_to_idx = {str(gid): i for i, gid in enumerate(self.df_games['game_id'])}
            self.sbert_model = SentenceTransformer('all-MiniLM-L6-v2')
            self.sbert_embeddings = np.load(os.path.join(ASSET_PATH, 'sbert_embeddings.npy'))
            
            # Muat dan proses histori untuk popularitas dan profil CF
            user_history_df = pd.read_pickle(os.path.join(ASSET_PATH, 'user_history.pkl'))
            self._calculate_popularity(user_history_df)
            self._create_training_user_profiles(user_history_df)

            # Muat dan proses rekomendasi CF
            cf_recs_raw = pd.read_parquet(os.path.join(ASSET_PATH, 'cf_recommendations.parquet'))
            game_id_map = pd.read_csv(os.path.join(ASSET_PATH, 'game_id_map.csv')).set_index('game_id_int')['game_id_str'].to_dict()
            exploded_df = cf_recs_raw.explode('recommendations')
            exploded_df['game_id'] = exploded_df['recommendations'].apply(lambda x: game_id_map.get(x['game_id_int']))
            self.cf_recs_map = exploded_df.dropna().groupby('user_id_int')['game_id'].apply(list).to_dict()

        except FileNotFoundError as e:
            print(f"GAGAL MEMUAT ASET: {e}")

    def _calculate_popularity(self, user_history_df):
        all_history_games = [game for sublist in user_history_df['history_ids'] for game in sublist]
        popularity = pd.Series(all_history_games).value_counts().reset_index()
        popularity.columns = ['game_id', 'popularity_score']
        self.popular_games_df = pd.merge(popularity, self.df_games, on='game_id').sort_values('popularity_score', ascending=False)

    def _create_training_user_profiles(self, user_history_df):
        print("Membuat profil selera untuk semua user di data training...")
        # Membuat dictionary {user_id: vector}
        user_history_map = user_history_df.set_index('user_id')['history_ids'].to_dict()
        user_profiles = {}
        for user_id, history_ids in user_history_map.items():
            history_indices = [self.game_id_to_idx[gid] for gid in history_ids if gid in self.game_id_to_idx]
            if history_indices:
                user_profiles[user_id] = np.average(self.sbert_embeddings[history_indices], axis=0)
        self.training_user_profiles = user_profiles
        
    # --- Fungsi untuk Fitur-Fitur Website ---

    def get_popular_recs(self, n=10):
        return self.popular_games_df.head(n)

    def get_similar_games(self, game_id, top_n=5):
        game_id = str(game_id)
        if game_id not in self.game_id_to_idx:
            return Game.objects.none()  # Kembalikan QuerySet kosong

        idx = self.game_id_to_idx[game_id]
        sim_scores = cosine_similarity(self.sbert_embeddings[idx].reshape(1, -1), self.sbert_embeddings)[0]
        sim_series = pd.Series(sim_scores, index=self.df_games['game_id']).drop(game_id, errors='ignore')
        top_recs_ids = sim_series.sort_values(ascending=False).head(top_n).index.tolist()

        # Kembalikan sebagai QuerySet
        return Game.objects.filter(game_id__in=top_recs_ids)

    def get_search_based_recs(self, query_text, n=10):
        if not query_text: return pd.DataFrame()
        query_vector = self.sbert_model.encode(query_text).reshape(1, -1)
        sim_scores = cosine_similarity(query_vector, self.sbert_embeddings)[0]
        sim_series = pd.Series(sim_scores, index=self.df_games['game_id'])
        top_recs_ids = sim_series.sort_values(ascending=False).head(n).index.tolist()
        return self.df_games[self.df_games['game_id'].isin(top_recs_ids)]

    def get_personalized_cbf_recs(self, user_history_ids, n=10):
        if not user_history_ids: return self.get_popular_recs(n)
        history_indices = [self.game_id_to_idx[gid] for gid in user_history_ids if gid in self.game_id_to_idx]
        if not history_indices: return self.get_popular_recs(n)
        user_profile_vector = np.average(self.sbert_embeddings[history_indices], axis=0).reshape(1, -1)
        sim_scores = cosine_similarity(user_profile_vector, self.sbert_embeddings)[0]
        sim_series = pd.Series(sim_scores, index=self.df_games['game_id']).drop(user_history_ids, errors='ignore')
        top_recs_ids = sim_series.sort_values(ascending=False).head(n).index.tolist()
        return self.df_games[self.df_games['game_id'].isin(top_recs_ids)]
    
    def get_cf_recs_via_proxy(self, user_history_ids, n=10):
        if not user_history_ids: return pd.DataFrame() # Jika user baru blm punya histori, CF blm bisa
        
        # 1. Buat profil selera untuk user web saat ini
        history_indices = [self.game_id_to_idx[gid] for gid in user_history_ids if gid in self.game_id_to_idx]
        if not history_indices: return pd.DataFrame()
        current_user_profile = np.average(self.sbert_embeddings[history_indices], axis=0).reshape(1, -1)
        
        # 2. Cari kembaran di data training
        training_users = list(self.training_user_profiles.keys())
        training_profiles = np.array([self.training_user_profiles[uid] for uid in training_users])
        
        sims = cosine_similarity(current_user_profile, training_profiles)[0]
        proxy_user_id = training_users[np.argmax(sims)]
        
        # 3. Ambil rekomendasi CF milik si kembaran
        # Perlu mapping dari user_id string ke int
        user_id_map_df = pd.read_csv(os.path.join(ASSET_PATH, 'user_id_map.csv'))
        proxy_user_int_id = user_id_map_df[user_id_map_df['user_id_str'] == proxy_user_id].iloc[0]['user_id_int']

        rec_ids = self.cf_recs_map.get(proxy_user_int_id, [])
        if not rec_ids: return pd.DataFrame()
        
        return self.df_games[self.df_games['game_id'].isin(rec_ids)].head(n)
    
    def get_similar_games_safe(self, game_id, top_n=5):
        try:
            game_obj = Game.objects.get(id=game_id)
        except Game.DoesNotExist:
            return Game.objects.none()

        # Step 1: Ambil hasil utama CBF
        main_similars = self.get_similar_games(game_obj.game_id, top_n=top_n)

        # Step 2: Kalau sudah cukup, return langsung
        if len(main_similars) >= top_n:
            return main_similars[:top_n]

        # Step 3: Fallback
        sisa = top_n - len(main_similars)
        fallback = Game.objects.filter(
            genre__icontains=game_obj.genre.split(',')[0].strip(),
            platform__icontains=game_obj.platform.split(',')[0].strip()
        ).exclude(id=game_obj.id)

        fallback = fallback.exclude(id__in=[g.id for g in main_similars])[:sisa]

        # Gabungkan dan kembalikan
        combined = list(main_similars) + list(fallback)
        return combined[:top_n]


