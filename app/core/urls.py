# core/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('neo_term_list/', views.get_neo_terms, name='neo_term_list'),
    path('/search', views.search, name='search'),
]
