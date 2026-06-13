from django.shortcuts import render

from .models import MensajeContacto


def index(request):
    return render(request, "home/index.html")


def contacto(request):
    mensaje_enviado = False

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        telefono = request.POST.get("telefono", "").strip()
        mensaje = request.POST.get("mensaje", "").strip()

        if nombre and telefono and mensaje:
            MensajeContacto.objects.create(
                nombre=nombre,
                telefono=telefono,
                mensaje=mensaje,
            )
            mensaje_enviado = True

    return render(
        request,
        "home/contacto.html",
        {"mensaje_enviado": mensaje_enviado},
    )
