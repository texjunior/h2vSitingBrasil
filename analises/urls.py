from django.urls import path
from . import views, laboratorio

app_name = "analises"

urlpatterns = [
    path("", views.mapa, name="mapa"),
    path("laboratorio/", laboratorio.painel, name="laboratorio"),
    path("api/perfil/", laboratorio.calcular, name="perfil_api"),
]
