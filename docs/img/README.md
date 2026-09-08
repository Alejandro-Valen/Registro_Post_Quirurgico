# Imágenes del README

Las tres capturas del panel del médico que aparecen en el `README.md` de la
raíz. Se generan con **datos ficticios**, nunca con los de un paciente real.

## Cómo regenerarlas

```bash
cd Registro_Post_Quirurgico
python manage.py seed_demo                                              # 1 paciente
python manage.py seed_demo_produccion --confirmar --medico demo_medico  # 2 más
python manage.py runserver
```

`seed_demo` imprime las credenciales al terminar. Los tres pacientes importan:
con uno solo el tablero **parece vacío** y no se entiende para qué sirve; con
tres se ven **dos casos urgentes y uno tranquilo**, que es lo que lo hace
legible de un vistazo.

Para retirarlos:

```bash
python manage.py seed_demo_produccion --limpiar --confirmar
python manage.py seed_demo --limpiar
```

## Qué muestra cada una

| Archivo | Dónde | Qué tiene que verse |
|---|---|---|
| `panel-triaje.png` | `/admin/` nada más entrar | Los cuatro indicadores y la lista ordenada por severidad, con el contador `×N`, el día postoperatorio y el teléfono |
| `detalle-alerta.png` | Alerta → bloque *Detecciones de la alerta* | La tabla completa de detecciones, con la severidad cambiando entre filas |
| `ficha-paciente.png` | Paciente → *Evolución signos vitales*, ventana de **10 días** | Las tres gráficas con sus umbrales punteados y la leyenda de los puntos rojos y los huecos |

Para la tercera, hay que pulsar **«10 días»** en el selector antes de capturar:
con la ventana por defecto se pierde el pico de fiebre.

## Reglas

- **Datos ficticios siempre.** Los pacientes de los seeds llevan el prefijo
  `DEMO —`, cédulas `DEMO-000X` y teléfonos reservados. Que se vean los
  teléfonos es deliberado: el médico los necesita sin abrir nada, y esa es la
  decisión de diseño que la captura muestra.
- **Texto alternativo descriptivo** en el `README.md`, no "captura de pantalla":
  hay que poder entender qué muestra la imagen sin verla.
- Si al capturar las gráficas salen **en blanco**, no es un problema de la
  captura: significa que Chart.js no cargó, y eso es un fallo que hay que
  reportar (ver `SECURITY.md` y `docs/trampas_conocidas.md`).
