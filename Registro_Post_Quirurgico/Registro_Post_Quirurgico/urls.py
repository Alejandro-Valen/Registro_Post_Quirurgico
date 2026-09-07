"""
URL configuration for Registro_Post_Quirurgico project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path

# B5: URL del admin configurable por variable de entorno para que no sea trivial.
# Valor por defecto intencional solo para desarrollo — en producción usar
# ADMIN_URL con un slug difícil de adivinar (ej. "gestion-clinica-x7k2/").
_ADMIN_URL = getattr(settings, 'ADMIN_URL', 'admin/')

urlpatterns = [
    path(_ADMIN_URL, admin.site.urls),
    path('', include('home.urls')),
    path('signos_sintomas/', include('signos_sintomas.urls')),
]
