import { useEffect, useState } from "react";
import { BookOpen, ClipboardCheck, FileText, Library, MessageCircle, Target } from "lucide-react";
import { useApp, useResumen } from "../../App.jsx";
import { api } from "../../api.js";
import { Avatar, Barra, Vista, fecha, useAccion } from "../../ui.jsx";
import { nombreDePila } from "../../validaciones.js";

const COLORES = { "Día 1": "var(--mint)", "Semana 1": "var(--sky)", "Mes 1": "var(--peach)" };
const TIPOS = { comentario: "Comentario", solicitud: "Solicitud", apoyo: "Apoyo", seguimiento: "Seguimiento" };

// Cada tipo de recomendación: ícono, texto del botón y a qué sección lleva.
const ACCIONES = {
  modulo: [BookOpen, "Ir al módulo", (r) => ["capacitacion", r.modulo_id ? { modulo: r.modulo_id } : {}]],
  evaluacion: [ClipboardCheck, "Ir a evaluaciones", (r) => ["evaluaciones", r.modulo_id ? { modulo: r.modulo_id } : {}]],
  documentos: [FileText, "Ir a documentos", () => ["documentos", {}]],
  material: [Library, "Preguntar al Tutor", () => ["tutor", {}]],
  tutor: [MessageCircle, "Abrir el Tutor", () => ["tutor", {}]],
};

/** Agente Recomendador: se pide aparte porque puede tardar unos segundos. Se vuelve a pedir si cambia el avance. */
function Recomendaciones({ ir, avance }) {
  const { config } = useApp();
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelado = false;
    setError("");
    api("/api/yo/recomendaciones")
      .then((r) => !cancelado && setDatos(r))
      .catch((e) => !cancelado && setError(e.status === 503 ? "" : e.message));
    return () => { cancelado = true; };
  }, [avance]);

  if (!datos && !error) {
    return (
      <div className="card mt agente-card" aria-live="polite">
        <div className="row"><span className="agente-ico"><Target size={18} strokeWidth={1.8} /></span><h3>Recomendaciones para ti</h3></div>
        <p className="muted small mt-s">{config.agentes?.recomendador || "El Agente Recomendador"} está revisando tu avance…</p>
      </div>
    );
  }
  if (!datos) return error ? <div className="notice mt small">El Agente Recomendador no está disponible por ahora. {error}</div> : null;

  return (
    <div className="card mt agente-card">
      <div className="row between wrap">
        <div className="row"><span className="agente-ico"><Target size={18} strokeWidth={1.8} /></span><h3>Recomendaciones para ti</h3></div>
        <span className="small muted">{datos.agente}</span>
      </div>
      <div className="stack mt">
        {datos.recomendaciones.map((r, i) => {
          const [Icono, boton, destino] = ACCIONES[r.tipo] || ACCIONES.tutor;
          return (
            <div key={i} className="recomendacion">
              <span className="mark now" aria-hidden="true"><Icono size={15} strokeWidth={1.8} /></span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <b>{r.titulo}</b>
                <div className="small muted">{r.motivo}</div>
                {r.pregunta_sugerida && <div className="small mt-s">Pregúntale: “{r.pregunta_sugerida}”</div>}
              </div>
              <button className="btn ghost sm" onClick={() => ir(...destino(r))}>{boton}</button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function Inicio({ ir }) {
  const resumen = useResumen();
  const [ejecutar] = useAccion();

  const marcar = async (t, hecha) => {
    await ejecutar(() => api(`/api/yo/tareas/${t.id}`, { metodo: "PUT", datos: { hecha } }));
    resumen.recargar();
  };

  return (
    <Vista estado={resumen}>
      {(d) => {
        const actual = d.modulos.find((m) => m.estado === "en_curso");
        const etapas = [...new Set(d.tareas.map((t) => t.etapa))];
        return (
          <>
            <div className="head">
              <h1>{nombreDePila(d.nombre) ? `Hola, ${nombreDePila(d.nombre)}` : "Hola"}</h1>
              <p className="muted">Llevas {d.avance}% de tu proceso de incorporación.</p>
            </div>
            <div className="grid g3">
              <div className="card corner tint-lav"><div className="small muted">Puesto</div><h3 className="mt-s">{d.puesto || "Sin asignar"}</h3></div>
              <div className="card tint-mint"><div className="small muted">Área</div><h3 className="mt-s">{d.area}</h3></div>
              <div className="card tint-peach"><div className="small muted">Fecha de ingreso</div><h3 className="mt-s">{fecha(d.fecha_ingreso, { day: "numeric", month: "long", year: "numeric" })}</h3></div>
            </div>

            {actual && (
              <div className="card mt row between wrap" style={{ borderColor: "var(--lav-2)" }}>
                <div style={{ flex: 1, minWidth: 220 }}>
                  <div className="small" style={{ color: "var(--lav-ink)" }}>Continúa donde lo dejaste</div>
                  <h3 className="mt-s">{actual.titulo}</h3>
                  <div className="mt-s" style={{ maxWidth: 320 }}><Barra valor={actual.total ? actual.leidas / actual.total * 100 : 0} /></div>
                </div>
                <button className="btn" onClick={() => ir("capacitacion", { modulo: actual.id })}>▷ Continuar</button>
              </div>
            )}

            <Recomendaciones ir={ir} avance={d.avance} />

            {d.observaciones.length > 0 && (
              <div className="notice peach mt">
                <b>Mensajes de tu supervisor</b>
                {d.observaciones.map((o, i) => (
                  <p key={i} className="mt-s"><span className="chip wait">{TIPOS[o.tipo] || o.tipo}</span> {o.texto} <span className="small muted">· {fecha(o.fecha)}</span></p>
                ))}
              </div>
            )}

            <h2 className="mt-l">Tu ruta</h2>
            <p className="muted small mt-s">Marca cada tarea cuando la termines.</p>
            <div className="road mt">
              {etapas.map((e) => (
                <div key={e}>
                  <span className="tag" style={{ background: COLORES[e] || "var(--lav)" }}>{e}</span>
                  {d.tareas.filter((t) => t.etapa === e).map((t) => (
                    <label key={t.id} className={`check ${t.hecha ? "done" : ""}`}>
                      <input type="checkbox" checked={t.hecha} onChange={(ev) => marcar(t, ev.target.checked)} />
                      <span>{t.titulo}</span>
                    </label>
                  ))}
                </div>
              ))}
            </div>

            <div className="grid g2 mt-l">
              <div className="card">
                <h3>Tu supervisor</h3>
                {d.supervisor ? (
                  <div className="row mt">
                    <Avatar u={d.supervisor} style={{ background: "var(--sky)", color: "var(--sky-ink)" }} />
                    <div><b>{d.supervisor.nombre}</b><div className="small muted">{d.supervisor.puesto}</div></div>
                  </div>
                ) : <p className="muted small mt-s">Aún no hay un supervisor registrado en tu área.</p>}
              </div>
              <div className="card corner tint-butter">
                <h3>¿No sabes qué sigue?</h3>
                <p className="small mt-s">Pregúntale al Tutor IA: te orienta según tu avance.</p>
                <button className="btn ghost sm mt" onClick={() => ir("tutor")}>Abrir Tutor</button>
              </div>
            </div>
          </>
        );
      }}
    </Vista>
  );
}
