# Bitácora del Proyecto — MVP Sugarbaker
## Clínica Somer — Medellín, Colombia

---

## Sprint 0 — Configuración Base y Seguridad
**Fecha:** 09/06/2026
**Responsable:** Alejandro (Dev) + León (Arquitecto IA)
**Estado:** COMPLETADO ✅

### Qué se hizo
- Diagnóstico del repositorio existente — identificados 3 problemas críticos:
  SECRET_KEY expuesta en GitHub, SQLite en vez de PostgreSQL, zona horaria UTC
- Instaladas dependencias: `python-decouple`, `psycopg2-binary`
- Creado archivo `.env` con SECRET_KEY nueva en cada máquina (nunca sube a GitHub)
- Creado `.env.example` como plantilla para el equipo
- Modificado `settings.py`: SECRET_KEY y DEBUG desde `.env`, base de datos
  cambiada a PostgreSQL, zona horaria a `America/Bogota`, idioma a `es-co`
- Generado `requirements.txt` con `pip freeze`
- Actualizado `.gitignore` para excluir `.env`
- Creado `CLAUDE.md` con contexto clínico completo del proyecto
- Creado `BITACORA.md` (este archivo)
- Push exitoso a rama `Desarrollo`
- Verificación: `python manage.py check` → 0 errores

### Decisiones tomadas
- `python-decouple` sobre `django-environ` — sintaxis más limpia
- PostgreSQL desde el día 0 — no migrar datos clínicos reales después
- `America/Bogota` es crítico para que los timestamps de reportes sean
  clínicamente correctos
- `BigAutoField` como DEFAULT_AUTO_FIELD — soporta hasta 9 mil millones
  de registros vs 2 millones del AutoField estándar

### Problemas encontrados y resueltos
- SECRET_KEY ya había estado expuesta en repo público → rotada inmediatamente
- El `settings.py` modificado no se había incluido en el commit del compañero →
  León lo recreó directamente en su máquina

---

## Sprint 1 — Modelos Clínicos y Base de Datos
**Fecha:** 10/06/2026 — 11/06/2026
**Responsable:** León (Arquitecto IA) con Claude Code
**Estado:** COMPLETADO ✅

### Qué se hizo

**Modelos clínicos (signos_sintomas/models.py):**
- Creado modelo `Paciente` con campos: nombre_completo, telefono_whatsapp
  (único, formato +57...), fecha_cirugia, medico_responsable, activo,
  fecha_registro
- Creado modelo `RegistroDiario` con las 6 variables clínicas del protocolo
  Sugarbaker: temperatura, dolor_eva, volumen_drenaje_ml, aspecto_drenaje,
  presencia_gases, episodios_nauseas. Campo `dia_postoperatorio` calculado
  automáticamente al guardar
- Creado modelo `Alerta` con tipos SEPSIS, FUGA_ANASTOMOTICA, ILEO_PARALITICO,
  DOLOR_AGUDO y severidades ALTA, MEDIA, BAJA. Campo `resuelta` para que el
  oncólogo marque alertas atendidas

**Panel del oncólogo (signos_sintomas/admin.py):**
- Registrados los 3 modelos con `@admin.register`
- Configurados `list_display`, `list_filter` y `search_fields` para cada modelo
- El oncólogo puede filtrar alertas por tipo, severidad y estado de resolución

**Base de datos PostgreSQL:**
- Instalado PostgreSQL 18 en máquina de León
- Creada base de datos `sugarbaker_db` via pgAdmin 4
- Ejecutado `makemigrations` → generado `0001_initial.py`
- Ejecutado `migrate` → 3 tablas clínicas creadas físicamente en PostgreSQL
- Creado superusuario `admin` para el panel

**Verificación:**
- `python manage.py runserver` exitoso
- Panel en http://127.0.0.1:8000/admin/ muestra: Alertas, Pacientes,
  Registros Diarios — todos en español con opciones Añadir y Modificar

### Decisiones tomadas
- `on_delete=PROTECT` en ForeignKey — Django no permite borrar un paciente
  que tenga registros diarios. Crítico para integridad de datos clínicos
- Aspecto del drenaje como `choices` cerradas (no texto libre) — el
  alert_engine necesita valores exactos para evaluar red flags
- `dia_postoperatorio` calculado automáticamente en `save()` — el oncólogo
  no cuenta días manualmente, el sistema lo sabe
- `fecha_resolucion` nullable — una alerta puede estar activa indefinidamente
  hasta que el médico la resuelva

### Problemas encontrados y resueltos
- Carpeta del proyecto tenía typo (`Resgistro_` en vez de `Registro_`) →
  resuelto via merge con rama sprint-1-frontend del compañero
- Conflicto de merge en settings.py → resuelto manualmente conservando
  configuración correcta de León (PostgreSQL + decouple)
- León no tenía permisos de escritura en GitHub → compañero lo agregó
  como colaborador
- `.env` estaba en carpeta vieja después del renombrado → copiado a nueva
  ubicación con comando `copy`

### Pendiente para Sprint 2
- Crear `signos_sintomas/alert_engine.py` con las 4 reglas clínicas
- Merge final sprint-1-modelos → Desarrollo

---

## Sprint 2 — Motor de Alertas
**Fecha:** 12/06/2026 — 13/06/2026
**Responsable:** León (Arquitecto IA) + Codex
**Estado:** COMPLETADO ✅

### Objetivo
Implementar `alert_engine.py` con función `evaluar_registro(registro)` que
evalúa un `RegistroDiario` y crea automáticamente objetos `Alerta` cuando
detecta red flags del protocolo Sugarbaker/HIPEC.

### Qué se hizo
- Creado `signos_sintomas/alert_engine.py` con la función `evaluar_registro`.
- Implementadas las 4 reglas clínicas del protocolo Sugarbaker/HIPEC.
- Agregadas constantes clínicas auditables para umbrales y valores críticos.
- Creadas 7 pruebas unitarias para reglas, valores límite y caso sin alertas.
- Verificación: `python manage.py test signos_sintomas` → 7 pruebas OK.
- Verificación: `python manage.py check` → 0 errores.

### Cierre de Sprint 2
1. Sprint 2 completado y mergeado a `Desarrollo` vía PR #1 (commits `b10ef97`,
   `40a2895`, merge `3bb8f05`). Incluye la resolución de la duplicación de
   modelos clínicos en `home/models.py`.
2. **NOTA DE PROCESO:** el merge de PR #1 ocurrió sin revisión formal del
   Arquitecto IA, en contra de la convención del equipo ("Ningún código
   clínico entra a `Desarrollo` sin aprobación del Arquitecto"). **Lección
   aprendida:** todo PR debe esperar aprobación explícita del Arquitecto antes
   del merge.
3. Bug detectado post-merge en la Regla 3 (sin gases 3 días consecutivos): el
   filtro/orden usaba `fecha_registro` (timestamp) en vez de
   `dia_postoperatorio` (concepto clínico exacto). Corregido directo en
   `Desarrollo` en el commit `01b8a47`.
4. Sprint 2 ahora cerrado: 7 pruebas unitarias OK y fix de Regla 3 aplicado
   y verificado.

---

## Sprint 3 — Bot WhatsApp
**Fecha:** pendiente
**Estado:** EN COLA ⏳

---

## Sprint 4 — Dashboard y Notificaciones
**Fecha:** pendiente
**Estado:** EN COLA ⏳

---

## Sprint 5 — Producción
**Fecha:** pendiente
**Estado:** EN COLA ⏳
