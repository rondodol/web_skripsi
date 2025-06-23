import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Avg
from django.http import JsonResponse, HttpResponse
from .forms import LoginForm, RegisterForm, RecommendForm, RatingForm
from .models import Game, GameRating, Collection, UserProfile
from .recommender import GameRecommender

recommender_instance = GameRecommender()

# ============================================
def get_all_genre_platform_choices():
    genres = recommender_instance.df_games['genres'].dropna().astype(str)
    platforms = recommender_instance.df_games['platforms'].dropna().astype(str)

    genre_set = set()
    platform_set = set()

    for g in genres:
        for item in g.replace("'", "").replace('"', '').split():
            cleaned = item.strip().title()
            if cleaned: genre_set.add(cleaned)

    for p in platforms:
        for item in p.replace("'", "").replace('"', '').split(','):
            cleaned = item.strip().title()
            if cleaned: platform_set.add(cleaned)

    genre_choices = sorted((g, g) for g in genre_set)
    platform_choices = sorted((p, p) for p in platform_set)
    return genre_choices, platform_choices

def user_login(request):
    if request.user.is_authenticated:
        return redirect('home') 

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            uname = form.cleaned_data['username']
            pwd = form.cleaned_data['password']
            user = authenticate(request, username=uname, password=pwd)
            if user:
                login(request, user)
                profile, created = UserProfile.objects.get_or_create(user=user)
                if created or (not profile.favorite_genres and not profile.favorite_platforms):
                    return redirect('preferences')
                return redirect('home')  # Ubah dari 'recommend' ke 'home'
            else:
                messages.error(request, "Username atau password salah.")
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})

@login_required
def user_logout(request):
    logout(request)
    return redirect('landing_or_redirect')

@login_required
def preferences(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    genre_choices, platform_choices = get_all_genre_platform_choices()

    if request.method == 'POST':
        genres_raw = request.POST.get('favorite_genres', '')
        platforms_raw = request.POST.get('favorite_platforms', '')
        profile.favorite_genres = genres_raw
        profile.favorite_platforms = platforms_raw
        profile.save()
        return redirect('home')  # pindahkan redirect hanya di POST

    # ini biarkan, jangan redirect otomatis agar data bisa ditampilkan
    return render(request, 'preferences.html', {
        'genre_choices': [g for g, _ in genre_choices],
        'platform_choices': [p for p, _ in platform_choices],
        'selected_genres': profile.favorite_genres.split(',') if profile.favorite_genres else [],
        'selected_platforms': profile.favorite_platforms.split(',') if profile.favorite_platforms else [],
    })

@login_required
def edit_preferences(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    genre_choices, platform_choices = get_all_genre_platform_choices()

    if request.method == 'POST':
        genres_raw = request.POST.get('favorite_genres', '')
        platforms_raw = request.POST.get('favorite_platforms', '')
        profile.favorite_genres = genres_raw
        profile.favorite_platforms = platforms_raw
        profile.save()
        messages.success(request, "Preferensi berhasil disimpan!")
        return redirect('home')

    return render(request, 'preferences.html', {
        'genre_choices': [g for g, _ in genre_choices],
        'platform_choices': [p for p, _ in platform_choices],
        'selected_genres': profile.favorite_genres.split(',') if profile.favorite_genres else [],
        'selected_platforms': profile.favorite_platforms.split(',') if profile.favorite_platforms else [],
    })

@login_required
def recommend_view(request):
    form = RecommendForm(request.GET or None)
    user = request.user

    queryset = Game.objects.none()
    if form.is_valid():
        game_name = form.cleaned_data.get('game_name', '').strip()
        genre = form.cleaned_data.get('genre', '').strip()
        platform = form.cleaned_data.get('platform', '').strip()

        # ⛔️ Cegah fallback global jika semua kosong
        if game_name or genre or platform:
            rec_df = recommender_instance.search_recommendations(game_name, genre, platform, top_n=15)
            queryset = Game.objects.filter(game_id__in=rec_df['game_id'].tolist())

    user_collections = set(Collection.objects.filter(user=user).values_list('game__game_id', flat=True))
    for game in queryset:
        game.in_collection = game.game_id in user_collections
        game.genre = game.genre.replace(',', ', ') if game.genre else '-'
        game.platform = game.platform.replace(',', ', ') if game.platform else '-'

    return render(request, 'recommend.html', {
        'form': form,
        'games': queryset,
    })

@login_required
def collection_view(request):
    koleksi = Collection.objects.filter(user=request.user)
    return render(request, 'collection.html', {'koleksi': koleksi})

def register_view(request):
    if request.user.is_authenticated:
        return redirect('recommend')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            uname = form.cleaned_data['username']
            pwd = form.cleaned_data['password1']
            user = User.objects.create_user(username=uname, password=pwd)
            login(request, user)
            return redirect('preferences')
    else:
        form = RegisterForm()
    return render(request, 'register.html', {'form': form})

@login_required
def game_detail(request, game_id):
    game = get_object_or_404(Game, game_id=game_id)
    game.genre = game.genre.replace(',', ', ') if game.genre else '-'
    game.platform = game.platform.replace(',', ', ') if game.platform else '-'
    in_collection = Collection.objects.filter(user=request.user, game=game).exists()

    try:
        existing_rating = GameRating.objects.get(user=request.user, game=game)
    except GameRating.DoesNotExist:
        existing_rating = None

    user_rating_value = existing_rating.rating_value if existing_rating else None

    if request.method == 'POST' and 'rating' in request.POST:
        form = RatingForm(request.POST)
        if form.is_valid():
            rating_value = int(form.cleaned_data['rating'])
            GameRating.objects.update_or_create(
                user=request.user,
                game=game,
                defaults={'rating_value': rating_value}
            )
            user_rating_value = rating_value
    else:
        form = RatingForm(initial={'rating': user_rating_value})

    avg_rating = GameRating.objects.filter(game=game).aggregate(avg=Avg('rating_value'))['avg'] or 0
    rating_count = GameRating.objects.filter(game=game).count()

    similar_games = recommender_instance.get_similar_games(game.game_id, top_n=5)
    for g in similar_games:
        g.in_collection = Collection.objects.filter(user=request.user, game=g).exists()
        g.genre = g.genre.replace(',', ', ') if g.genre else '-'
        g.platform = g.platform.replace(',', ', ') if g.platform else '-'

    return render(request, 'game_detail.html', {
        'game': game,
        'form': form,
        'avg_rating': round(avg_rating, 1),
        'rating_count': rating_count,
        'in_collection': in_collection,
        'user_rating_value': user_rating_value,
        'similar_games': similar_games
    })

def landing_or_redirect(request):
    if request.user.is_authenticated:
        try:
            profile = request.user.profile  # atau user.userprofile
            if not profile.favorite_genres and not profile.favorite_platforms:
                return redirect('preferences')
        except:
            pass
        return redirect('home')
    return render(request, 'landing.html')

@login_required
def home_view(request):
    user = request.user
    profile = UserProfile.objects.get(user=user)

    # Ambil game yang sudah dikoleksi user
    user_collections = set(Collection.objects.filter(user=user).values_list('game__game_id', flat=True))

    # === FITUR 3: Hybrid (Mungkin Anda Menyukai)
    hybrid_df = recommender_instance.get_hybrid_recommendations(
        user_genres=profile.favorite_genres or '',
        user_platforms=profile.favorite_platforms or '',
        user_id=str(user.id),
        top_n=30  # Ambil lebih banyak dulu
    )
    hybrid_df = hybrid_df[~hybrid_df['game_id'].isin(user_collections)].head(10)
    hybrid_games = Game.objects.filter(game_id__in=hybrid_df['game_id'].tolist())

    # === FITUR 4: Pure CF (User Lain Juga Menyukai)
    cf_df = recommender_instance.get_cf_recommendations(int(user.id), top_n=30)
    cf_df = cf_df[~cf_df['game_id'].isin(user_collections)].head(10)

    # Cek apakah CF punya hasil
    cf_games = []
    if not cf_df.empty:
        cf_games = Game.objects.filter(game_id__in=cf_df['game_id'].tolist())

    # Tandai game yang sudah dikoleksi
    for g in list(hybrid_games) + list(cf_games):
        g.in_collection = g.game_id in user_collections
        g.genre = g.genre.replace(',', ', ') if g.genre else '-'
        g.platform = g.platform.replace(',', ', ') if g.platform else '-'

    return render(request, 'home.html', {
        'recommended_games': hybrid_games,
        'other_users_liked': cf_games,  # kosong = tidak ditampilkan di template
    })

@login_required
def toggle_collection(request, game_id):
    user = request.user
    game = get_object_or_404(Game, game_id=game_id)
    collection_entry = Collection.objects.filter(user=user, game=game).first()

    if collection_entry:
        collection_entry.delete()
        messages.info(request, f"{game.name} dihapus dari koleksi Anda.")
    else:
        Collection.objects.create(user=user, game=game)
        messages.success(request, f"{game.name} ditambahkan ke koleksi Anda.")

    return redirect(request.META.get('HTTP_REFERER', 'home'))

@login_required
def collection_view(request):
    user = request.user
    collections = Collection.objects.filter(user=user).select_related('game')
    return render(request, 'collection.html', {'collections': collections})

def export_user_ratings(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="user_web_rating.csv"'
    writer = csv.writer(response)
    writer.writerow(['user_id', 'game_id', 'rating'])
    for rating in GameRating.objects.all():
        writer.writerow([rating.user.id, rating.game.game_id, rating.rating_value])
    return response

