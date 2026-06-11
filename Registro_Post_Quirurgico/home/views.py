from django.shortcuts import render

# Página principal
def index(request):
    return render(request, 'home/index.html')

# Página de contacto
def contacto(request):
    return render(request, 'home/contacto.html')