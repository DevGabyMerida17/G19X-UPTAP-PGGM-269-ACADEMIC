// Cliente de la API de FastAPI. El token de sesión vive en Redis (backend);
// aquí solo se recuerda en el navegador para no pedir login en cada recarga.
const CLAVE = "p1_token";

export const sesion = {
  get() { try { return localStorage.getItem(CLAVE); } catch { return null; } },
  set(t) { try { localStorage.setItem(CLAVE, t); } catch { /* sin almacenamiento */ } },
  borrar() { try { localStorage.removeItem(CLAVE); } catch { /* sin almacenamiento */ } },
};

export class ErrorApi extends Error {
  constructor(mensaje, status, codigo = null) { super(mensaje); this.status = status; this.codigo = codigo; }
}

function mensajeDeError(datos, status) {
  if (typeof datos?.detail === "string") return datos.detail;
  if (datos?.detail?.mensaje) return datos.detail.mensaje;
  if (Array.isArray(datos?.detail)) {
    // Errores de validación de Pydantic
    return datos.detail.map((d) => String(d.msg || "").replace(/^Value error, /, "")).join(" ");
  }
  return status >= 500 ? "El servidor no respondió. Intenta de nuevo." : "Algo salió mal.";
}

// Se llama cuando la sesión deja de ser válida (expiró o la cuenta fue dada de baja).
let alExpirar = () => {};
export const onSesionExpirada = (fn) => { alExpirar = fn; };

export async function api(ruta, { metodo = "GET", datos, archivo } = {}) {
  const headers = {};
  const token = sesion.get();
  if (token) headers.Authorization = `Bearer ${token}`;
  let body;
  if (archivo) {
    body = new FormData();
    body.append("archivo", archivo);
  } else if (datos !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(datos);
  }
  let r;
  try {
    r = await fetch(ruta, { method: metodo, headers, body });
  } catch {
    throw new ErrorApi("No hay conexión con el servidor.", 0);
  }
  const contenido = r.headers.get("content-type")?.includes("json") ? await r.json() : null;
  if (!r.ok) {
    const error = new ErrorApi(mensajeDeError(contenido, r.status), r.status, contenido?.detail?.codigo || null);
    if (token && (r.status === 401 || error.codigo === "cuenta_inactiva" || error.codigo === "cambio_obligatorio")) alExpirar(error);
    throw error;
  }
  return contenido;
}

/** Trae un archivo protegido (con la sesión) como Blob, sin descargarlo. */
export async function obtenerArchivo(ruta) {
  let r;
  try {
    r = await fetch(ruta, { headers: { Authorization: `Bearer ${sesion.get()}` } });
  } catch {
    throw new ErrorApi("No hay conexión con el servidor.", 0);
  }
  if (!r.ok) throw new ErrorApi("No se pudo abrir el archivo.", r.status);
  return r.blob();
}

export async function descargar(ruta, nombre, blob = null) {
  const url = URL.createObjectURL(blob || await obtenerArchivo(ruta));
  const a = Object.assign(document.createElement("a"), { href: url, download: nombre });
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function wsUrl(ruta) {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}${ruta}?token=${encodeURIComponent(sesion.get() || "")}`;
}
