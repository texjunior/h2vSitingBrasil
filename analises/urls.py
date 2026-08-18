from django.urls import path
from . import views

app_name = "analises"

urlpatterns = [
    path("", views.mapa, name="mapa"),
]
