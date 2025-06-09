import csv
from django.core.management.base import BaseCommand
from main.models import Game

class Command(BaseCommand):
    help = 'Import games from games_with_esrb.csv'

    def handle(self, *args, **kwargs):
        with open('games_with_esrb.csv', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            count = 0
            for row in reader:
                name = row.get('name')
                genre = row.get('genres') or 'Unknown'
                platform = row.get('platforms') or 'Unknown'
                description = row.get('description', '')
                released = row.get('released', '')
                cover_image = row.get('cover_image', '')

                if name:  # skip if name is empty
                    Game.objects.update_or_create(
                        game_id=row['game_id'],
                        defaults={
                            'name': row['name'],
                            'genre': row['genres'],
                            'platform': row['platforms'],
                            'description': row['description'],
                            'released': row['released'],
                            'cover_image': row['cover_image']
                        }
                    )

                    count += 1
            self.stdout.write(self.style.SUCCESS(f'Successfully imported {count} games.'))
