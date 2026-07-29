# Auditoria independiente pre-merge de los Loops 1-6

## Instruccion para Claude Code

Actua como auditor senior independiente de seguridad, Django, Twilio y sistemas
que procesan datos clinicos. No asumas que las decisiones previas son correctas
por estar documentadas ni implementes correcciones durante esta revision. Tu
trabajo es contrastar documentacion, codigo, migraciones, pruebas y configuracion
de produccion, y emitir un veredicto reproducible antes del PR a `Desarrollo`.

### Repositorio y alcance

- Repositorio local: `Registro_Post_Quirurgico`.
- Rama a auditar: `sprint-5-produccion`.
- Base de comparacion: `origin/Desarrollo`.
- Punto funcional esperado antes de esta documentacion: `0d12d88` o un commit
  documental posterior que no cambie comportamiento.
- El diff actual contra `origin/Desarrollo` contiene aproximadamente 70 archivos,
  10.576 inserciones y 1.556 eliminaciones. Revisa archivos completos, no solo
  el diff.
- No edites archivos, no crees migraciones, no hagas commits, no hagas push, no
  abras PR y no hagas merge. Entrega exclusivamente el informe.
- Hay un archivo raiz no rastreado llamado
  `FORMATO_CONSENTIMIENTO_HABEAS_DATA.md`. No lo agregues, modifiques ni borres.

### Lectura obligatoria previa

Lee completos `docs/README.md`, `CLAUDE.md`,
`ROADMAP_MONITOREO_POSQUIRURGICO.md`, `BITACORA.md`,
`docs/proceso/auditorias/2026-06_informe_sprint3_cierre.md`, `docs/cron_setup.md`,
`docs/railway_deploy.md`, `docs/transferencia_cuentas.md` y el consentimiento
rastreado dentro de `docs/`. Despues inspecciona el proyecto completo, incluidos
`settings.py`, `settings_production.py`, `urls.py`, `wsgi.py`, `asgi.py`,
Dockerfile, dependencias, comandos, templates, estaticos y todas las migraciones.

### Contexto funcional de los seis loops

1. **Integridad clinica.** Se corrigio el calculo historico del dia
   posoperatorio; resolver una alerta exige motivo; los datos clinicos quedan
   acotados por medico e inmutables donde corresponde; se agregaron restricciones
   de BD; y `crear_medico` provisiona una cuenta staff de privilegio minimo sin
   reutilizar superusuarios.
2. **Confiabilidad.** `MessageSid` se reclama en PostgreSQL; recepcion, avance de
   conversacion y efectos se coordinan transaccionalmente; cada registro conserva
   estado de evaluacion y admite reintento; la BD impide dos alertas abiertas del
   mismo paciente/tipo; y la conversacion queda ligada al check-in exacto.
3. **Experiencia medica.** Se ajustaron contraste y ancho del panel; los pendientes
   se acumulan hasta resolverse; historial y graficas usan 3/7/10 dias; los
   mensajes de contacto se asignan y filtran por medico; y `DeteccionAlerta`
   explica cada incremento del contador xN sin inventar datos historicos.
4. **Produccion.** Django 6.0.7 y dependencias directas fijadas; CSP activo;
   Chart.js local; IP real de Railway aceptada solo bajo confianza explicita;
   correo ALTA desacoplado mediante outbox; Resend usa HTTPS, timeout,
   idempotencia y reintentos; el correo es generico y no contiene PHI/PII.
5. **Validacion.** Hay pruebas de firma Twilio, SID concurrente, outbox
   concurrente, rollback del motor, flujo completo y carga. La medicion registrada
   fue 50 pacientes, 550 webhooks y 50 registros en 5,03 segundos. Tambien se
   completo un flujo normal real en el Sandbox.
6. **Cierre tecnico.** Se completaron flujos reales MEDIA y ALTA; se descubrio y
   corrigio una respuesta silenciosa al superar el limite de 20 mensajes/hora;
   se verifico el reintento del correo; se actualizo Requests a 2.33.0 por
   PYSEC-2026-2275; se limpio el paciente ficticio; y se repitieron suite, checks,
   auditoria de dependencias, escaneo de secretos y smoke de produccion.

Commits de referencia, sin asumir que sean correctos: `49596e8`, `442ccc2`,
`5ad1b71`, `5d6b379`, `3c86487`, `c12bfe5` y `0d12d88`.

### Comandos minimos que debes ejecutar

Usa el entorno del proyecto y registra comando, resultado y cualquier limitacion:

```powershell
git status --short --branch
git fetch origin Desarrollo sprint-5-produccion
git diff --stat origin/Desarrollo...HEAD
git diff origin/Desarrollo...HEAD
cd Registro_Post_Quirurgico
python manage.py test
python manage.py makemigrations --check --dry-run
python manage.py check
pip-audit -r ..\requirements-runtime.txt
```

Ejecuta tambien `check --deploy` con
`Registro_Post_Quirurgico.settings_production`, usando valores temporales no
secretos y sintacticamente validos para todas las variables obligatorias. No
conectes ese check a bases, Redis, Twilio o Resend reales. El resultado esperado
es cero issues. La suite esperada es **280 tests OK** y `pip-audit` no debe
encontrar vulnerabilidades conocidas en `requirements-runtime.txt`.

No confundas los conflictos de `pip check` del Python global de Windows
(`googletrans`/herramientas de notebooks y versiones antiguas de `httpx`) con el
runtime de Railway: el Dockerfile instala exclusivamente
`requirements-runtime.txt`. Si detectas un problema, demuestra primero que
afecta ese runtime reproducible.

### Revision obligatoria

1. **Aislamiento por medico:** intenta demostrar que un staff no-superuser puede
   listar, abrir por URL, cambiar, resolver o borrar pacientes, registros,
   check-ins, alertas, detecciones o mensajes de otro medico. Revisa acciones,
   inlines, autocomplete, filtros, historiales y rutas personalizadas del Admin.
2. **Webhook Twilio:** verifica firma fail-closed con header ausente, vacio,
   repetido o malformado, body vacio, Content-Type inesperado, URL/proxy y token
   ausente. Confirma que los errores no exponen stacktrace, datos clinicos ni
   estructura interna.
3. **Idempotencia y atomicidad:** estudia duplicados seriales y concurrentes del
   mismo SID, fallo entre efectos, reintento posterior, locks, restricciones y
   estados incompletos. Busca registros, alertas, detecciones o correos duplicados.
4. **Rate limiting:** valida identidad de cliente, Redis compartido, fallback,
   expiracion, atomicidad de `cache.incr()` y respuesta al paciente. Comprueba que
   un cuestionario legitimo de 10 preguntas no se bloquee y analiza dos flujos
   completos dentro de una hora. El limite no debe permitir falsificar IP desde
   `X-Forwarded-For`.
5. **Datos medicos:** busca PHI/PII en logs, excepciones, correos, outbox,
   respuestas HTTP, mensajes de rate limit, fixtures, seeds, migraciones e historial
   Git. El correo generico sin datos del paciente es una decision de seguridad.
6. **Alertas:** revisa umbrales, agrupacion por paciente/tipo, contador `veces`,
   `DeteccionAlerta`, escalamiento, resolucion obligatoria, restricciones e
   idempotencia. FR no genera alertas de manera intencional.
7. **Correo:** valida que el webhook nunca dependa de la red de Resend; que timeout,
   backoff, elegibilidad, locks e idempotencia eviten perdidas y duplicados; y que
   errores persistidos no incluyan secretos ni contenido clinico.
8. **Configuracion de produccion:** revisa `DEBUG`, `SECRET_KEY`, hosts, URL privada
   del Admin, HTTPS/HSTS/cookies, CSRF, CORS, CSP, WhiteNoise, Axes, Redis, proxy,
   PostgreSQL, logging y defaults peligrosos. Confirma que un valor faltante falle
   de forma segura.
9. **Secretos y dependencias:** busca credenciales reales en archivos rastreados,
   historial, migraciones y ejemplos. Audita solo las dependencias efectivas del
   runtime y confirma soporte de seguridad de Django/Python.
10. **Migraciones y datos:** lee todas las migraciones y especialmente los
    `RunPython` 0019 y 0020. Evalua irreversibilidad, bloqueo, datos legacy,
    consolidacion de duplicados y seguridad al desplegar sobre datos existentes.
11. **Carga y tiempos:** inspecciona consultas del webhook y motor, indices, N+1,
    full scans, contencion y cualquier operacion de red. Contrasta la prueba de
    carga con el timeout de Twilio y determina sus limites metodologicos.
12. **Superficie web:** verifica que no existan endpoints medicos publicos, que
    `/admin/` sea 404, que la ruta privada exija autenticacion y que templates/
    scripts no introduzcan XSS ni dependencias remotas incompatibles con CSP.
13. **Operacion:** contrasta comandos y documentacion de Railway. Revisa que el
    cron frecuente recupere evaluaciones y correos, y que cerrar check-ins sea
    idempotente. Detecta diferencias entre el codigo y los horarios documentados,
    y evalua la falta de monitoreo externo del scheduler.
14. **Cobertura:** identifica caminos criticos no cubiertos aunque los 280 tests
    pasen. No uses el numero de tests como sustituto de revisar su calidad.

### Hechos y pendientes que debes clasificar correctamente

- La validacion de firma de Twilio ya fue diseñada fail-safe, pero debe auditarse.
- FR sin alertas es comportamiento clinico intencional.
- No agregues datos clinicos al correo para hacerlo mas descriptivo.
- `enviar_recordatorios` sigue siendo un stub: el bot actual es reactivo y el
  paciente debe escribir primero. Evalua esto como brecha para un piloto con
  recordatorios proactivos, y por separado si bloquea un PR a `Desarrollo`.
- El Sandbox debe sustituirse por WhatsApp Business, numero aprobado, facturacion
  y plantillas antes de pacientes reales.
- Resend necesita dominio propio con SPF/DKIM/DMARC; `onboarding@resend.dev` puede
  llegar a spam.
- El plan actual de Railway reutiliza temporalmente `cron-tarde` cada 5 minutos.
  Tras el upgrade se necesita un `cron-operativo` separado y restaurar el horario
  de tarde.
- Railway todavía no tiene una alarma externa que detecte una ejecución de cron
  omitida o una caída total. Los reintentos internos recuperan trabajo fallido,
  pero no prueban que el scheduler siga arrancando.
- Deben completarse y firmarse los marcadores del Habeas Data antes del primer
  paciente real.
- La landing conserva datos del medico entre corchetes y el aviso de boceto.
- RAG/OpenMed estan diferidos expresamente a Sprint 6.
- Los datos de las pruebas manuales fueron ficticios y se eliminaron. No asumas
  que los demos documentados siguen presentes sin verificarlo.

Separa siempre estos dos veredictos:

1. **Apto para abrir PR y fusionar a `Desarrollo`.** Evalua calidad, seguridad,
   regresiones, migraciones y coherencia del alcance implementado.
2. **Apto para piloto real con pacientes.** Incluye dependencias externas,
   operacion, legal, dominio de correo y WhatsApp Business.

Un pendiente externo documentado no bloquea automaticamente el PR a
`Desarrollo`, pero cualquier vulnerabilidad explotable, perdida/duplicacion de
datos clinicos, aislamiento roto, migracion insegura, prueba critica fallida o
configuracion de produccion insegura si debe bloquearlo.

### Formato de entrega

Presenta hallazgos primero, ordenados por severidad. Usa exactamente:

```text
HALLAZGO: descripcion concreta
EVIDENCIA: archivo y linea exacta, prueba o comando reproducible
SEVERIDAD: CRITICO / ALTO / MEDIO / BAJO
BLOQUEA PR/MERGE: SI / NO
BLOQUEA PILOTO REAL: SI / NO
RECOMENDACION: accion concreta, sin implementarla
PRUEBA FALTANTE: caso que debe agregarse, o NINGUNA
```

Incluye despues:

- Resultados de todos los comandos y pruebas.
- Discrepancias entre documentacion y codigo.
- Riesgos residuales y limites de la auditoria.
- Lista separada de requisitos externos para el piloto real.
- Una linea final para el merge: `APROBADO PARA PR A DESARROLLO` o
  `BLOQUEADO PARA PR A DESARROLLO - motivo`.
- Una linea final independiente: `APTO PARA PILOTO REAL` o
  `NO APTO PARA PILOTO REAL - requisitos pendientes`.

Si no encuentras hallazgos bloqueantes, dilo expresamente; no inventes un
hallazgo para justificar la auditoria. Si una comprobacion no puede ejecutarse,
no la des por aprobada: registra la limitacion y su impacto en el veredicto.
