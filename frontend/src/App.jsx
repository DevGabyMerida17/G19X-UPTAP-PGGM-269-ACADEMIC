import {
  BookOpen, ChartPie, ClipboardCheck, FileText, FolderCheck, House, Layers, LayoutDashboard, Library, ListChecks,
  Bot, LogOut, MessageCircle, Users,
} from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, onSesionExpirada, sesion } from "./api.js";
import { olvidarCuenta } from "./microsoft.js";
import { Barra, BotonTema, Cargando, ErrorCaja, Marca, iniciales, useApi } from "./ui.jsx";
import Acceso from "./paginas/Acceso.jsx";
import NuevaPassword from "./paginas/NuevaPassword.jsx";
import CambioObligatorio from "./paginas/CambioObligatorio.jsx";
import Inicio from "./paginas/colaborador/Inicio.jsx";
import Documentos from "./paginas/colaborador/Documentos.jsx";
import Capacitacion from "./paginas/colaborador/Capacitacion.jsx";
import Evaluaciones from "./paginas/colaborador/Evaluaciones.jsx";
import Tutor from "./paginas/colaborador/Tutor.jsx";
import Avance from "./paginas/colaborador/Avance.jsx";
import Panel from "./paginas/rh/Panel.jsx";
import Colaboradores from "./paginas/rh/Colaboradores.jsx";
import Programas from "./paginas/rh/Programas.jsx";
import Revision from "./paginas/rh/Revision.jsx";
import Conocimiento from "./paginas/rh/Conocimiento.jsx";
import Actividades from "./paginas/rh/Actividades.jsx";
import AsistenteRH from "./paginas/rh/AsistenteRH.jsx";
import Equipo from "./paginas/supervisor/Equipo.jsx";
import { nombreVisible } from "./validaciones.js";

const MENUS = {
  colaborador: {
    nombre: "Colaborador",
    paginas: [
      ["inicio", House, "Inicio", Inicio], ["documentos", FileText, "Documentos", Documentos],
      ["capacitacion", BookOpen, "Capacitación", Capacitacion], ["evaluaciones", ClipboardCheck, "Evaluaciones", Evaluaciones],
      ["tutor", MessageCircle, "Tutor IA", Tutor], ["avance", ChartPie, "Mi avance", Avance],
    ],
  },
  rh: {
    nombre: "Recursos Humanos",
    paginas: [
      ["panel", LayoutDashboard, "Panel", Panel], ["colaboradores", Users, "Personal", Colaboradores],
      ["programas", Layers, "Programas y módulos", Programas], ["revision", FolderCheck, "Documentos", Revision],
      ["conocimiento", Library, "Base del Tutor IA", Conocimiento], ["actividades", ListChecks, "Actividades", Actividades],
      ["asistente", Bot, "Asistente de RH", AsistenteRH],
    ],
  },
  supervisor: { nombre: "Supervisor", paginas: [["equipo", Users, "Mi equipo", Equipo]] },
};

/* Contexto compartido: usuario, configuración y navegación */
const AppCtx = createContext(null);
export const useApp = () => useContext(AppCtx);

/* El resumen del colaborador se comparte entre páginas para que el avance se actualice en todas */
const ResumenCtx = createContext(null);
export const useResumen = () => useContext(ResumenCtx);

export default function App() {
  const [config, setConfig] = useState(null);
  const [usuario, setUsuario] = useState(undefined); // undefined = verificando sesión
  const [errorInicio, setErrorInicio] = useState("");
  const [aviso, setAviso] = useState(null); // mensaje para la pantalla de acceso (p. ej. cuenta dada de baja)
  // Enlace recibido por correo: ?activar=... o ?restablecer=...
  const [enlace, setEnlace] = useState(() => {
    const q = new URLSearchParams(window.location.search);
    return q.get("activar") || q.get("restablecer") || null;
  });

  const salir = useCallback(async () => {
    try { await api("/api/auth/salir", { metodo: "POST" }); } catch { /* ya no importa */ }
    sesion.borrar();
    olvidarCuenta();
    setUsuario(null);
  }, []);

  useEffect(() => {
    onSesionExpirada((error) => {
      if (error.codigo === "cambio_obligatorio") {  // sigue con la contraseña temporal
        setUsuario((u) => (u ? { ...u, debe_cambiar_password: true } : u));
        return;
      }
      sesion.borrar();
      setUsuario(null);
      setAviso(error.codigo === "cuenta_inactiva"
        ? { tipo: "baja", texto: error.message }
        : { tipo: "info", texto: "Tu sesión terminó. Vuelve a iniciar sesión." });
    });
    (async () => {
      try {
        setConfig(await api("/api/config"));
      } catch (e) {
        setErrorInicio(e.message);
        return;
      }
      if (!sesion.get()) { setUsuario(null); return; }
      try { setUsuario(await api("/api/auth/yo")); } catch { sesion.borrar(); setUsuario((u) => u ?? null); }
    })();
  }, []);

  const entrar = (r) => { sesion.set(r.token); setAviso(null); setUsuario(r.usuario); };
  const terminarEnlace = (mensaje) => {
    window.history.replaceState(null, "", window.location.pathname);
    setEnlace(null);
    if (mensaje) setAviso({ tipo: "ok", texto: mensaje });
  };

  if (errorInicio) return <div className="login"><div className="form"><ErrorCaja mensaje={`No se pudo conectar con la API: ${errorInicio}`} reintentar={() => location.reload()} /></div></div>;
  if (!config || usuario === undefined) return <div className="login"><Cargando /></div>;
  if (enlace) return <NuevaPassword token={enlace} alTerminar={terminarEnlace} />;
  if (!usuario) return <Acceso config={config} alEntrar={entrar} aviso={aviso} />;
  if (usuario.debe_cambiar_password) return <CambioObligatorio usuario={usuario} alTerminar={entrar} salir={salir} />;
  return (
    <AppCtx.Provider value={{ usuario, config }}>
      <Plataforma usuario={usuario} salir={salir} />
    </AppCtx.Provider>
  );
}

function Plataforma({ usuario, salir }) {
  const menu = MENUS[usuario.rol];
  const [pagina, setPagina] = useState(menu.paginas[0][0]);
  const [params, setParams] = useState({});
  const ir = useCallback((p, extra = {}) => { setPagina(p); setParams(extra); window.scrollTo(0, 0); }, []);
  const Actual = menu.paginas.find((p) => p[0] === pagina)[3];

  // Verifica que la cuenta siga activa: al cambiar de sección, al volver a la pestaña y cada minuto.
  // Si RH la dio de baja, api() avisa y se muestra el mensaje en la pantalla de acceso.
  useEffect(() => { api("/api/auth/yo").catch(() => {}); }, [pagina]);
  useEffect(() => {
    const revisar = () => { if (document.visibilityState === "visible") api("/api/auth/yo").catch(() => {}); };
    const t = setInterval(revisar, 60000);
    document.addEventListener("visibilitychange", revisar);
    return () => { clearInterval(t); document.removeEventListener("visibilitychange", revisar); };
  }, []);

  const contenido = (
    <>
      <header className="topbar">
        <div className="marca"><Marca /><span className="marca-sub">Onboarding</span></div>
        <div className="who">
          <div className="name small" style={{ textAlign: "right" }}><b>{nombreVisible(usuario.nombre)}</b><div className="muted">{menu.nombre}</div></div>
          <BotonTema />
          <div className="avatar">{iniciales(usuario.nombre)}</div>
          <button className="btn ghost sm" onClick={salir}><LogOut size={15} strokeWidth={1.8} />Salir</button>
        </div>
      </header>
      <div className="layout">
        <aside className="side">
          {usuario.rol === "colaborador" ? <ProgresoLateral /> : <div className="rol-lateral">{menu.nombre}</div>}
          <nav className="nav" aria-label="Secciones">
            {menu.paginas.map(([id, Icono, texto]) => (
              <button key={id} className={pagina === id ? "on" : ""} aria-current={pagina === id ? "page" : undefined} onClick={() => ir(id)}>
                <span className="ico" aria-hidden="true"><Icono size={18} strokeWidth={1.8} /></span>{texto}
              </button>
            ))}
          </nav>
        </aside>
        <main><Actual ir={ir} params={params} /></main>
      </div>
    </>
  );
  return usuario.rol === "colaborador" ? <ProveedorResumen>{contenido}</ProveedorResumen> : contenido;
}

function ProveedorResumen({ children }) {
  const estado = useApi("/api/yo/resumen");
  return <ResumenCtx.Provider value={estado}>{children}</ResumenCtx.Provider>;
}

/** Porcentaje de cada etapa: el círculo se va cerrando conforme avanzas. */
export function etapasDe(d) {
  const pct = (hechos, total) => (total ? Math.round((hechos / total) * 100) : 100);
  const tareas = (etapa) => d.tareas.filter((t) => t.etapa === etapa);
  const dia1 = tareas("Día 1");
  const cierre = [...tareas("Semana 1"), ...tareas("Mes 1")];
  // Un documento en revisión cuenta la mitad; validado cuenta completo.
  const docs = d.documentos.reduce((s, x) => s + (x.estado === "validado" ? 1 : x.estado === "revision" ? 0.5 : 0), 0);
  // Un módulo en curso cuenta según las secciones leídas.
  const mods = d.modulos.reduce((s, m) => s + (m.estado === "completado" ? 1 : m.total ? (m.leidas / m.total) * 0.9 : 0), 0);
  return [
    ["Bienvenida", pct(dia1.filter((t) => t.hecha).length, dia1.length)],
    ["Documentos", pct(docs, d.documentos.length)],
    ["Capacitación", pct(mods, d.modulos.length)],
    ["Cierre", pct(cierre.filter((t) => t.hecha).length, cierre.length)],
  ];
}

export function Anillo({ valor, tam = 22 }) {
  const r = 9;
  const c = 2 * Math.PI * r;
  if (valor >= 100) {
    return (
      <svg className="anillo" width={tam} height={tam} viewBox="0 0 22 22" role="img" aria-label="Completado">
        <circle cx="11" cy="11" r="10" fill="var(--mint)" stroke="var(--mint-ink)" strokeWidth="1.5" />
        <path d="M6.5 11.5l3 3 6-6.5" fill="none" stroke="var(--mint-ink)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  return (
    <svg className="anillo" width={tam} height={tam} viewBox="0 0 22 22" role="img" aria-label={`${valor}% completado`}>
      <circle cx="11" cy="11" r={r} fill="none" stroke="var(--line)" strokeWidth="2.5" />
      {valor > 0 && (
        <circle cx="11" cy="11" r={r} fill="none" stroke="var(--lav-ink)" strokeWidth="2.5" strokeLinecap="round"
          strokeDasharray={`${(valor / 100) * c} ${c}`} transform="rotate(-90 11 11)" />
      )}
    </svg>
  );
}

function ProgresoLateral() {
  const { datos } = useResumen();
  if (!datos) return <div className="prog" />;
  return (
    <div className="prog">
      <div className="row between small"><span>Progreso general</span><b>{datos.avance}%</b></div>
      <div className="mt-s"><Barra valor={datos.avance} /></div>
      <div className="mt etapas">
        {etapasDe(datos).map(([t, v]) => (
          <div key={t} className="etapa">
            <Anillo valor={v} />
            <span className={v >= 100 ? "hecha" : v > 0 ? "" : "muted"}>{t}</span>
            <span className="small muted pct">{v >= 100 ? "Listo" : `${v}%`}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
