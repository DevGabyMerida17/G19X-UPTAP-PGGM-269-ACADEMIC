/* Inicio de sesión con Microsoft Entra ID (MSAL). La librería se carga solo cuando se usa. */

// Microsoft regresa a la página con ?code=...&state=... (o #code=...) al terminar el inicio de sesión.
export const esRespuestaDeMicrosoft = () =>
  /[#?&]state=/.test(window.location.hash + window.location.search) &&
  /[#?&](code|error)=/.test(window.location.hash + window.location.search);

/** Si esta pestaña es la ventana de Microsoft que vuelve a la plataforma, le pasa la respuesta
    a la página que la abrió (ventana emergente) o a la página de inicio (misma pestaña). */
export async function reenviarRespuesta() {
  const { broadcastResponseToMainFrame } = await import("@azure/msal-browser/redirect-bridge");
  await broadcastResponseToMainFrame();
}

async function cliente(entra) {
  const { PublicClientApplication } = await import("@azure/msal-browser");
  const msal = new PublicClientApplication({
    auth: {
      clientId: entra.client_id,
      authority: `https://login.microsoftonline.com/${entra.tenant_id}`,
      redirectUri: window.location.origin,
    },
  });
  await msal.initialize();
  return msal;
}

const PERMISOS = { scopes: ["openid", "profile", "email"] };

/** Abre la ventana de Microsoft. Si el navegador la bloquea, continúa en la misma pestaña:
    en ese caso la página se va a Microsoft y regresa, y devuelve null. */
export async function iniciarSesion(entra) {
  const msal = await cliente(entra);
  // Un intento anterior que quedó a medias (ventana cerrada o bloqueada) impediría empezar otro.
  await msal.handleRedirectPromise().catch(() => null);
  try { sessionStorage.removeItem("msal.interaction.status"); } catch { /* sin almacenamiento */ }
  try {
    return (await msal.loginPopup(PERMISOS)).idToken;
  } catch (err) {
    if (err?.errorCode !== "popup_window_error" && err?.errorCode !== "empty_window_error") throw err;
    await msal.loginRedirect(PERMISOS);
    return null;
  }
}

/** Al volver del inicio de sesión en la misma pestaña, entrega el token (o null si no hay nada pendiente). */
export async function respuestaPendiente(entra) {
  let pendiente = false;
  try {
    pendiente = Object.keys(sessionStorage).some((k) => k.startsWith(`msal.${entra.client_id}.urlHash`));
  } catch { /* sin acceso al almacenamiento: no hay respuesta pendiente */ }
  if (!pendiente) return null;
  const r = await (await cliente(entra)).handleRedirectPromise();
  return r?.idToken || null;
}
