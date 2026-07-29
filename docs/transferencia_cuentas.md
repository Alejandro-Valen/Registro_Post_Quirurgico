# Protocolo de Transferencia de Cuentas al Médico

> Sprint 5, Bloque 6. Basado en las decisiones de producto confirmadas en
> sesión el 01/07/2026 — ver ROADMAP_MONITOREO_POSQUIRURGICO.md, FASE 5,
> tabla de decisiones P-1 a P-15.
>
> Estado actualizado al 21/07/2026: infraestructura piloto desplegada en
> Railway; transferencia comercial y requisitos para pacientes reales siguen
> pendientes.

## Modelo de negocio (P-1, P-2, P-13)

Un solo médico cliente. El equipo (León y Alejandro) son los
administradores técnicos del sistema mientras el médico lo usa — las
cuentas de los servicios de infraestructura están a nombre del equipo, no
del médico, hasta que el producto se venda. El médico llama al equipo si
algo falla (P-3: mantenimiento con intervención mínima — cron falla →
email automático → resolución en ~30 min).

## Cuentas del proyecto (titularidad del equipo hasta la venta)

| Servicio | Propósito | Estado actual | Quién transfiere |
|---|---|---|---|
| Railway | Web, PostgreSQL, Redis y cron | Desplegado y verificado; el plan actual obliga a reutilizar temporalmente `cron-tarde` cada 5 minutos | León/Alejandro → Médico |
| Twilio | Recepción de WhatsApp del bot | Sandbox activo y probado; faltan WhatsApp Business, número propio, facturación, plantillas y envío saliente | León/Alejandro → Médico |
| Correo del sistema / Resend | Notificaciones genéricas de alerta ALTA | Resend por HTTPS entregó una prueba real; se usa temporalmente `onboarding@resend.dev` | León/Alejandro → Médico |
| Dominio propio | Remitente de correo y URL pública propia | URL Railway activa; dominio propio y autenticación SPF/DKIM/DMARC pendientes | León/Alejandro → Médico |
| Cuenta de correo del proyecto | Propiedad de Resend y contacto técnico | `seguimientolionalejo@gmail.com` usada para pruebas; definir titularidad definitiva antes de transferir | León/Alejandro → Médico |

## Protocolo de transferencia (al momento de la venta)

1. El médico crea sus propias cuentas en Railway, Twilio, Resend y correo
   (o el equipo le ayuda a crearlas, pero quedan a su nombre).
2. El equipo hace un deploy limpio en las nuevas cuentas del médico,
   usando el mismo código de la rama `Desarrollo` (o el último tag
   estable).
3. Se transfieren las variables de entorno (`.env` de producción) de
   forma segura — en persona, o cifradas (nunca por WhatsApp/email plano,
   nunca subidas a GitHub).
4. Se verifica el funcionamiento completo en las cuentas nuevas: bot de
   WhatsApp responde, alertas se generan, email de alerta ALTA llega,
   cron corre.
5. Se eliminan las cuentas del equipo del servidor de producción viejo
   (o se apaga ese despliegue).
6. El médico recibe el manual de operación (sección siguiente).

## Lo que el médico necesita saber operar (manual mínimo)

- **Cómo entrar al panel:** URL del admin + su usuario y contraseña.
  En desarrollo el default es `/admin/`; en producción se usa la ruta privada
  configurada con `ADMIN_URL`. Compartir la URL por un canal seguro y no
  escribir el slug real en documentación pública.
- **Cómo registrar un paciente nuevo:** nombre completo, cédula
  (obligatoria y única desde Sprint 5, Bloque 1), teléfono de WhatsApp en
  formato internacional (`+57...`), fecha de la cirugía, tipo de cirugía
  (opcional, solo estadístico), y asignarse a sí mismo como médico
  responsable.
- **Cómo interpretar las alertas:** severidad ALTA (ir a urgencias/llamar
  ya), MEDIA (llamar al paciente), BAJA (monitorear) — visible como badge
  de color en la lista de Alertas del admin.
- **Permisos de la cuenta médica:** puede crear/actualizar sus pacientes,
  consultar registros y check-ins sin alterarlos, revisar mensajes de contacto
  y resolver alertas mediante el flujo controlado. No puede borrar datos
  clínicos ni acceder a usuarios, grupos o configuración técnica.
- **Cómo marcar una alerta como resuelta:** seleccionarla en la lista y
  usar la acción "Marcar como resuelta". Las alertas no se pueden borrar
  (solo un superusuario puede, y no es el flujo normal) — es trazabilidad
  clínica obligatoria.
- **Cómo ver la evolución de un paciente:** entrar a su ficha — ahí están
  las gráficas de temperatura/dolor/FC (selector 3/7/10 días, sin
  recargar la página) y la tabla de historial (con su propio selector de
  días, Sprint 5 Bloque 3B/4).
- **Cuándo se desactiva un paciente:** automáticamente a los 10 días
  postoperatorios, o manualmente desde su ficha en cualquier momento
  (Sprint 5, Bloque 1B, decisión P-5).
- **A quién llamar si algo falla:** contacto directo del equipo (agregar
  aquí el teléfono/email real antes de la entrega final — no inventado en
  este documento).

## Pendiente antes de que el médico use el sistema con pacientes reales

- **HABEAS DATA (P-15, Sprint 5 Bloque 7):** consentimiento informado
  mínimo — el contenido legal/clínico lo redacta o valida el médico, no
  se inventa en código. Bloquea el uso con pacientes reales, no el resto
  del despliegue técnico.
- Completar salida del Sandbox: WhatsApp Business, número propio, facturación,
  plantillas aprobadas e implementación real de `enviar_recordatorios`.
- Verificar un dominio propio en Resend con SPF/DKIM/DMARC y comprobar entrega
  fuera de spam.
- Mejorar el plan Railway, separar `cron-operativo` y configurar monitoreo
  externo que avise si web o cron dejan de ejecutarse.
- Sustituir los marcadores de la landing por los datos definitivos del médico.
- Definir el contacto real de soporte del equipo (teléfono/email) antes
  de escribirlo en la sección de manual de operación de arriba.
