from django.urls import path
from django.shortcuts import redirect
from . import views

urlpatterns = [
    path('', views.landing_or_redirect, name='landing_or_redirect'), 
    path('home/', views.home_view, name='home'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('register/', views.register_view, name='register'),
    path('preferences/', views.preferences, name='preferences'),
    path('recommend/', views.recommend_view, name='recommend'),
    path('collection/', views.collection_view, name='collection'),
    path('game/<str:game_id>/', views.game_detail, name='game_detail'),
    path('edit_preferences/', views.edit_preferences, name='edit_preferences'),
    path('game/<str:game_id>/toggle_collection/', views.toggle_collection, name='toggle_collection'),
    path('koleksi/', views.collection_view, name='collection'),
    path('recommend/', views.recommend_view, name='recommend'),
]

