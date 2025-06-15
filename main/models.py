from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Game(models.Model):
    game_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    genre = models.CharField(max_length=255)
    platform = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    released = models.CharField(max_length=100, blank=True, null=True)
    tags = models.TextField(blank=True, null=True)
    background_image = models.URLField(blank=True, null=True)

    def save(self, *args, **kwargs):
        # Bersihkan spasi ekstra di genre dan platform
        if self.genre:
            self.genre = ','.join([g.strip() for g in self.genre.split(',')])
        if self.platform:
            self.platform = ','.join([p.strip() for p in self.platform.split(',')])
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    favorite_genres = models.TextField(blank=True)
    favorite_platforms = models.TextField(blank=True)

    def __str__(self):
        return self.user.username

class Collection(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE, to_field='game_id', db_column='game_id')

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

class GameRating(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE, to_field='game_id', db_column='game_id')
    rating_value = models.FloatField()

    class Meta:
        unique_together = ('user', 'game')

    def __str__(self):
        return f"{self.user.username} rated {self.game.name} as {self.rating_value}"

