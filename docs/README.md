# Mapa y estado de la documentacion

> Ultima revision integral: 21/07/2026. Rama `sprint-5-produccion`.

Este indice distingue la documentacion vigente de los registros historicos. Si
dos documentos parecen contradecirse, usa el orden de autoridad indicado abajo
y verifica siempre el codigo real.

## Fuentes vigentes

1. `CLAUDE.md`: memoria operativa, arquitectura actual, protocolo de cierre y
   punto exacto de reanudacion.
2. `ROADMAP_MONITOREO_POSQUIRURGICO.md`: decisiones de producto, checklists y
   requisitos separados para merge y para piloto real.
3. `AUDITORIA_PRE_MERGE_LOOPS_1_6.md`: instruccion obligatoria para la segunda
   opinion de Claude Code antes del PR a `Desarrollo`.
4. `docs/railway_deploy.md`: topologia, variables y despliegue actual.
5. `docs/cron_setup.md`: programacion y limitaciones operativas de los cron.
6. `docs/transferencia_cuentas.md`: propiedad y entrega futura de servicios y
   credenciales.
7. `Registro_Post_Quirurgico/.env.example`: nombres de variables y ejemplos no
   secretos. Nunca es un archivo listo para copiar en produccion sin revisar.

`BITACORA.md` es la cronologia de ejecucion. Es acumulativa: las afirmaciones de
una sesion antigua describen el estado de ese momento y pueden haber sido
superadas por entradas posteriores. La entrada mas reciente manda para el
estado operativo, pero no reemplaza la verificacion del codigo.

## Material historico o de referencia

- `AUDITORIA_SPRINT3_CIERRE.md` conserva el diagnostico previo al hardening. Sus
  hallazgos no deben reportarse como actuales sin volver a reproducirlos.
- `docs/auditoria_literatura/` conserva analisis clinicos de junio de 2026. Las
  frases "pendiente" dentro de esos analisis pertenecen a la sesion original;
  las decisiones vigentes estan en `CLAUDE.md` y el roadmap.
- `Registro_Post_Quirurgico/signos_sintomas/knowledge_base.md` es un placeholder
  para Sprint 6. No es un corpus RAG activo ni sustituye validacion medica.
- `Chart.js-LICENSE.md` es una licencia de proveedor y no se edita como memoria
  del proyecto.

## Documento legal canonico

La version rastreada y canonica es
`docs/FORMATO_CONSENTIMIENTO_HABEAS_DATA.md`. Sigue requiriendo completar los
campos entre corchetes, revision final del responsable y firma de cada paciente
antes del uso real.

Existe localmente una copia raiz no rastreada con el mismo nombre. Al cierre del
21/07/2026 ambas copias tenian el mismo SHA-256, pero la copia raiz no forma
parte del repositorio y no debe agregarse automaticamente a commits o PR.

## Punto seguro de pausa

- Rama: `sprint-5-produccion`, sincronizada con `origin` antes de este barrido.
- Punto funcional desplegado: `0d12d88`.
- Cierre documental preexistente: `998403a`; este barrido es solo documental.
- Ultima suite funcional: 280/280 tests OK con Requests 2.33.0.
- `makemigrations --check`, `manage.py check`, `check --deploy` y `pip-audit`
  quedaron limpios en el cierre del Loop 6.
- Flujos reales NORMAL, MEDIA y ALTA verificados en el Sandbox; datos ficticios
  de esas pruebas eliminados.
- No existe PR a `Desarrollo` ni autorizacion de merge.

## Siguiente sesion

1. Abrir el repositorio en la rama `sprint-5-produccion` y traer cambios de
   origin sin mezclar otras ramas.
2. Leer este indice, `CLAUDE.md` y
   `AUDITORIA_PRE_MERGE_LOOPS_1_6.md` completos.
3. Pedir a Claude Code que ejecute la auditoria sin editar, commitear, publicar
   ni fusionar.
4. Volver con el informe completo para clasificar hallazgos junto con Codex.
5. Resolver y probar los bloqueantes. Solo despues preparar el PR.

## Todavia no apto para pacientes reales

Aunque la rama puede ser candidata a merge tras la auditoria, el piloto real
sigue bloqueado por WhatsApp Business y el envio saliente de recordatorios, un
dominio propio autenticado en Resend, monitoreo externo del cron/web, separacion
del cron operativo al mejorar el plan Railway, consentimiento completado y
firmado, y datos definitivos del medico en la landing.

No guardar claves, tokens, contrasenas, numeros reales de pacientes ni contenido
clinico en esta documentacion, commits, chats o informes de auditoria.
