"""Envío de correos: bienvenida con datos de acceso, activación de cuenta y cambio de contraseña."""
import html
import logging
import smtplib
import ssl
import uuid
from email.message import EmailMessage

from . import config

log = logging.getLogger("correo")


def _plantilla(titulo: str, saludo: str, texto: str, boton: str, enlace: str, nota: str, bloque: str = "") -> str:
    # Estilos en línea porque los clientes de correo ignoran las hojas de estilo.
    return f"""<!doctype html><html><body style="margin:0;background:#F6F2EA;font-family:Arial,Helvetica,sans-serif;color:#231F3A">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px">
<table cellpadding="0" cellspacing="0" style="margin-bottom:18px"><tr>
<td style="width:40px;height:40px;background:#A898EA;border-radius:12px;text-align:center;color:#FFFFFF;font-size:20px;font-weight:bold">&#9634;</td>
<td style="padding-left:12px;font-family:Georgia,serif;font-size:26px;font-weight:bold">Pluri<span style="color:#5A47B8">One</span></td>
</tr></table>
<table width="480" cellpadding="0" cellspacing="0" style="max-width:480px;background:#FFFFFF;border-radius:22px;border-top:6px solid #B7A8EE">
<tr><td style="padding:30px 30px 28px">
<h1 style="font-family:Georgia,serif;font-size:22px;margin:0 0 12px">{titulo}</h1>
<p style="margin:0 0 12px">{saludo}</p>
<p style="margin:0 0 20px;line-height:1.55;color:#4A4660">{texto}</p>
{bloque}
<a href="{enlace}" style="display:inline-block;background:#B7A8EE;color:#231F3A;padding:13px 26px;border-radius:14px;text-decoration:none;font-weight:bold">{boton}</a>
<p style="margin:22px 0 0;font-size:13px;color:#6B6880;line-height:1.55">{nota}<br>Si el botón no funciona, copia este enlace en tu navegador:<br>{enlace}</p>
</td></tr></table>
<p style="font-size:12px;color:#8F8AA3;margin-top:16px">PluriOne · Develop Talent &amp; Technology · Ciudad de México</p>
</td></tr></table></body></html>"""


def enviar(destinatario: str, asunto: str, texto_plano: str, html: str) -> None:
    msg = EmailMessage()
    msg["From"] = config.SMTP_FROM
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg.set_content(texto_plano)
    msg.add_alternative(html, subtype="html")

    if not config.SMTP_HOST:
        # Sin servidor de correo configurado: se guarda el correo para poder revisarlo en pruebas.
        config.CORREOS_DIR.mkdir(parents=True, exist_ok=True)
        ruta = config.CORREOS_DIR / f"{uuid.uuid4().hex[:8]}-{destinatario.replace('@', '_at_')}.eml"
        ruta.write_bytes(bytes(msg))
        log.warning("SMTP no configurado: el correo para %s se guardó en %s", destinatario, ruta)
        return

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as s:
        if config.SMTP_STARTTLS:
            s.starttls(context=ssl.create_default_context())
        if config.SMTP_USER:
            s.login(config.SMTP_USER, config.SMTP_PASSWORD)
        s.send_message(msg)
    log.info("Correo '%s' enviado a %s", asunto, destinatario)


def enviar_seguro(*args) -> bool:
    """Igual que enviar(), pero registra el error en lugar de romper la petición."""
    try:
        enviar(*args)
        return True
    except Exception:
        log.exception("No se pudo enviar el correo")
        return False


def invitacion(nombre: str, correo: str, token: str) -> bool:
    enlace = f"{config.APP_URL}/?activar={token}"
    nombre_corto = nombre.split()[0]
    return enviar_seguro(
        correo,
        "Bienvenido a PluriOne: activa tu cuenta",
        f"Hola, {nombre_corto}.\n\nRecursos Humanos creó tu cuenta en la plataforma de onboarding de PluriOne. "
        f"Para entrar, crea tu contraseña en este enlace (vence en {config.HORAS_ENLACE_ACTIVACION} horas):\n\n{enlace}\n",
        _plantilla("Activa tu cuenta", f"Hola, {nombre_corto}.",
                   "Recursos Humanos creó tu cuenta en la plataforma de onboarding de PluriOne. "
                   "Para entrar, crea tu contraseña.",
                   "Crear mi contraseña", enlace,
                   f"El enlace vence en {config.HORAS_ENLACE_ACTIVACION} horas."),
    )


def restablecer(nombre: str, correo: str, token: str) -> bool:
    enlace = f"{config.APP_URL}/?restablecer={token}"
    nombre_corto = nombre.split()[0]
    return enviar_seguro(
        correo,
        "Restablece tu contraseña de PluriOne",
        f"Hola, {nombre_corto}.\n\nRecibimos una solicitud para cambiar tu contraseña. Usa este enlace "
        f"(vence en {config.MINUTOS_ENLACE_RESTABLECER} minutos):\n\n{enlace}\n\n"
        "Si no fuiste tú, ignora este correo; tu contraseña no cambiará.\n",
        _plantilla("Restablece tu contraseña", f"Hola, {nombre_corto}.",
                   "Recibimos una solicitud para cambiar la contraseña de tu cuenta.",
                   "Cambiar contraseña", enlace,
                   f"El enlace vence en {config.MINUTOS_ENLACE_RESTABLECER} minutos. "
                   "Si no fuiste tú, ignora este correo; tu contraseña no cambiará."),
    )


def bienvenida(nombre: str, correo: str, password_temporal: str, nueva_cuenta: bool = True) -> bool:
    """Datos de acceso que RH genera al dar de alta (o al crear una nueva contraseña temporal)."""
    enlace = config.APP_URL
    nombre_corto = nombre.split()[0]
    titulo = "Bienvenido a PluriOne" if nueva_cuenta else "Tu nueva contraseña temporal"
    intro = ("Recursos Humanos creó tu cuenta en la plataforma de bienvenida de PluriOne. "
             "Estos son tus datos para entrar:") if nueva_cuenta else (
        "Recursos Humanos generó una nueva contraseña temporal para tu cuenta. Estos son tus datos para entrar:")
    nota = ("Al entrar por primera vez te pediremos crear tu propia contraseña; la temporal dejará de funcionar. "
            "No compartas este correo con nadie.")
    bloque = f"""<table width="100%" cellpadding="0" cellspacing="0" style="background:#F4F1FD;border-radius:14px;margin:0 0 22px">
<tr><td style="padding:14px 18px 6px;font-size:12px;color:#6B6880;text-transform:uppercase;letter-spacing:.05em">Usuario (correo)</td></tr>
<tr><td style="padding:0 18px 12px;font-size:16px;font-weight:bold">{html.escape(correo)}</td></tr>
<tr><td style="padding:4px 18px 6px;font-size:12px;color:#6B6880;text-transform:uppercase;letter-spacing:.05em">Contraseña temporal</td></tr>
<tr><td style="padding:0 18px 16px;font-family:Consolas,'Courier New',monospace;font-size:20px;font-weight:bold;letter-spacing:.06em">{html.escape(password_temporal)}</td></tr>
</table>"""
    return enviar_seguro(
        correo,
        "Bienvenido a PluriOne: tus datos de acceso" if nueva_cuenta else "PluriOne: tu nueva contraseña temporal",
        f"Hola, {nombre_corto}.\n\n{intro}\n\nUsuario (correo): {correo}\nContraseña temporal: {password_temporal}\n\n"
        f"Entra en: {enlace}\n\n{nota}\n",
        _plantilla(titulo, f"Hola, {html.escape(nombre_corto)}.", intro, "Entrar a la plataforma", enlace, nota, bloque),
    )
