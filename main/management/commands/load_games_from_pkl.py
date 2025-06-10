from django.core.management.base import BaseCommand
from main.models import Game
import pandas as pd
import os

class Command(BaseCommand):
    help = 'Load games from games_df.pkl into the Game model'

    def handle(self, *args, **kwargs):
        file_path = 'main/assets/games_df.pkl'
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"File tidak ditemukan: {file_path}"))
            return

        df = pd.read_pickle(file_path)
        self.stdout.write(f"Memuat {len(df)} game dari {file_path}")

        count = 0
        for _, row in df.iterrows():
            game, created = Game.objects.get_or_create(
                game_id=row['game_id'],
                defaults={
                    'name': row.get('name', ''),
                    'genre': row.get('genres', ''),
                    'platform': row.get('platforms', ''),
                    'description': row.get('description', ''),
                    'released': row.get('released', ''),
                    'tags': row.get('tags', ''),
                    'background_image': row.get('background_image', ''),
                }
            )
            if created:
                count += 1

        self.stdout.write(self.style.SUCCESS(f"{count} game berhasil dimasukkan."))
