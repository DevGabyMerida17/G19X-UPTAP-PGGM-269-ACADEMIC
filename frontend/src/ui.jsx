import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { Box, Check, Circle, Lock, Moon, Play, Sun } from "lucide-react";
import { api, wsUrl } from "./api.js";

/* ---------- Tema claro / oscuro ---------- */
// index.html ya puso data-tema antes de cargar; aquí solo se cambia y se recuerda.
export function BotonTema({ className = "" }) {
  const [tema, setTema] = useState(() => document.documentElement.getAttribute("data-tema") || "claro");
  const cambiar = () => {
    const nuevo = tema === "oscuro" ? "claro" : "oscuro";
    document.documentElement.setAttribute("data-tema", nuevo);
    try { localStorage.setItem("p1_tema", nuevo); } catch { /* sin almacenamiento: dura solo esta visita */ }
    setTema(nuevo);
  };
  const oscuro = tema === "oscuro";
  return (
    <button type="button" className={`boton-tema ${className}`} onClick={cambiar}
      aria-label={oscuro ? "Cambiar a modo claro" : "Cambiar a modo oscuro"} title={oscuro ? "Modo claro" : "Modo oscuro"}>
      {oscuro ? <Sun size={18} strokeWidth={1.8} /> : <Moon size={18} strokeWidth={1.8} />}
    </button>
  );
}

/* ---------- Avisos breves (toast) ---------- */
const AvisoCtx = createContext(() => {});
export const useAviso = () => useContext(AvisoCtx);

export function ProveedorAvisos({ children }) {
  const [texto, setTexto] = useState("");
  const timer = useRef();
  const avisar = useCallback((t) => {
    setTexto(t);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setTexto(""), 2600);
  }, []);
  return (
    <AvisoCtx.Provider value={avisar}>
      {children}
      {texto && <div className="toast" role="status">{texto}</div>}
    </AvisoCtx.Provider>
  );
}

/* ---------- Datos de la API ---------- */
export function useApi(ruta) {
  const [estado, setEstado] = useState({ datos: null, error: null, cargando: true });
  const recargar = useCallback(async () => {
    try {
      const datos = await api(ruta);
      setEstado({ datos, error: null, cargando: false });
    } catch (e) {
      setEstado((s) => ({ ...s, error: e.message, cargando: false }));
    }
  }, [ruta]);
  useEffect(() => { recargar(); }, [recargar]);
  return { ...estado, recargar };
}

/** Recarga datos cuando el backend publica un cambio (Redis pub/sub -> WebSocket). */
export function useEventos(alCambiar) {
  const fn = useRef(alCambiar);
  fn.current = alCambiar;
  useEffect(() => {
    let ws, cerrado = false, reintento;
    const conectar = () => {
      ws = new WebSocket(wsUrl("/ws/eventos"));
      ws.onmessage = (e) => { try { fn.current(JSON.parse(e.data)); } catch { /* ignorar */ } };
      ws.onclose = (e) => { if (!cerrado && e.code !== 4401) reintento = setTimeout(conectar, 3000); };
    };
    conectar();
    return () => { cerrado = true; clearTimeout(reintento); ws?.close(); };
  }, []);
}

/* ---------- Piezas visuales ---------- */
export const Barra = ({ valor, tono = "" }) => (
  <div className={`bar ${tono}`} role="progressbar" aria-valuenow={valor} aria-valuemin={0} aria-valuemax={100}>
    <i style={{ width: `${Math.max(0, Math.min(100, valor))}%` }} />
  </div>
);

const ESTADOS = {
  en_curso: ["info", "En curso"], completado: ["ok", "Completado"], retrasado: ["bad", "Retrasado"],
  inactivo: ["off", "Inactivo"], pendiente: ["off", "Sin subir"], revision: ["wait", "En revisión"],
  validado: ["ok", "Validado"], rechazado: ["bad", "Rechazado"], bloqueado: ["off", "Bloqueado"],
};
export const Chip = ({ estado, children }) => {
  const [cls, txt] = ESTADOS[estado] || ["off", estado];
  return <span className={`chip ${cls}`}>{children || txt}</span>;
};
export const tonoBarra = (estado) => (estado === "completado" ? "mintbar" : estado === "retrasado" ? "rosebar" : "");

/** Nombre de la empresa como logotipo: "Pluri" en tinta y "One" en lila. */
export const Marca = ({ grande = false }) => (
  <span className={`logotipo ${grande ? "grande" : ""}`}>
    <span className={`logo-tile ${grande ? "grande" : ""}`} aria-hidden="true"><Box size={grande ? 26 : 17} strokeWidth={1.8} /></span>
    <span>Pluri<span className="one">One</span></span>
  </span>
);

/** Marca circular del estado de un módulo: completado, en curso o bloqueado/pendiente. */
export function MarcaEstado({ estado, bloqueado = "lock" }) {
  if (estado === "completado") return <span className="mark ok" aria-hidden="true"><Check size={15} strokeWidth={2.4} /></span>;
  if (estado === "en_curso") return <span className="mark now" aria-hidden="true"><Play size={13} strokeWidth={2.2} /></span>;
  return (
    <span className="mark lock" aria-hidden="true">
      {bloqueado === "lock" ? <Lock size={13} strokeWidth={2} /> : <Circle size={10} strokeWidth={2.4} />}
    </span>
  );
}

export const Cargando = () => <p className="cargando">Cargando…</p>;
export const ErrorCaja = ({ mensaje, reintentar }) => (
  <div className="notice rose row between wrap">
    <span>{mensaje}</span>
    {reintentar && <button className="btn ghost sm" onClick={reintentar}>Reintentar</button>}
  </div>
);

export function Vista({ estado, children }) {
  if (estado.cargando && !estado.datos) return <Cargando />;
  if (estado.error && !estado.datos) return <ErrorCaja mensaje={estado.error} reintentar={estado.recargar} />;
  return children(estado.datos);
}

export const iniciales = (n = "") => n.trim().split(/\s+/).map((x) => x[0]).join("").slice(0, 2).toUpperCase();

export function fecha(iso, opciones = { day: "numeric", month: "short" }) {
  if (!iso) return "";
  const d = iso.length === 10 ? new Date(`${iso}T12:00`) : new Date(iso);
  return d.toLocaleDateString("es-MX", opciones).replace(".", "");
}

/** Ejecuta una acción de la API mostrando el error si falla. */
export function useAccion() {
  const avisar = useAviso();
  const [ocupado, setOcupado] = useState(false);
  const ejecutar = useCallback(async (fn, exito) => {
    setOcupado(true);
    try {
      const r = await fn();
      if (exito) avisar(exito);
      return r;
    } catch (e) {
      avisar(e.message);
      return undefined;
    } finally {
      setOcupado(false);
    }
  }, [avisar]);
  return [ejecutar, ocupado];
}
