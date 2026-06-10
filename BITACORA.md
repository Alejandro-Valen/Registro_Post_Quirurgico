# Bitácora del Proyecto — MVP Sugarbaker

## Formato de cada entrada
**Fecha | Sprint | Responsable | Qué se hizo | Decisiones tomadas**

---

## Sprint 0 — Configuración base y seguridad
**Fecha:** 09/06/2025
**Responsable:** Alejandro (Dev) + Arquitecto IA
**Estado:** COMPLETADO ✅

### Qué se hizo
- Clonado y diagnóstico del repositorio existente
- Identificados 3 problemas críticos: SECRET_KEY expuesta,
  SQLite en vez de PostgreSQL, zona horaria incorrecta
- Instaladas dependencias: `python-decouple`, `psycopg2-binary`
- Creado archivo `.env` con SECRET_KEY nueva (nunca en GitHub)
- Creado `.env.example` como plantilla para el equipo
- Modificado `settings.py`: SECRET_KEY y DEBUG desde `.env`,
  base de datos cambiada a PostgreSQL, zona horaria a
  `America/Bogota`, idioma a `es-co`
- Generado `requirements.txt` con `pip freeze`
- Actualizado `.gitignore` para excluir `.env`
- Push exitoso a rama `Desarrollo`
- Verificación: `python manage.py check` → 0 errores

### Decisiones tomadas
- Se usa `python-decouple` sobre `django-environ` por su
  sintaxis más limpia y menor overhead
- PostgreSQL desde el día 0 para no migrar datos clínicos
  reales después
- Zona horaria `America/Bogota` es crítica para que los
  timestamps de los reportes diarios sean clínicamente correctos

### Pendiente para Sprint 1
- Crear modelos: `Paciente`, `RegistroDiario`, `Alerta`
- Ejecutar migraciones en PostgreSQL
- Registrar modelos en admin.py

---
## Sprint 1 — Modelos clínicos
**Fecha:** pendiente
**Responsable:** pendiente
**Estado:** EN COLA ⏳