import { useResumen } from "../../App.jsx";
import { api } from "../../api.js";
import { Barra, Vista, fecha, iniciales, useAccion } from "../../ui.jsx";

const COLORES = { "Día 1": "var(--mint)", "Semana 1": "var(--sky)", "Mes 1": "var(--peach)" };
const TIPOS = { comentario: "Comentario", solicitud: "Solicitud", apoyo: "Apoyo", seguimiento: "Seguimiento" };

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
              <h1>Hola, {d.nombre.split(" ")[0]}</h1>
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
                    <div className="avatar" style={{ background: "var(--sky)", color: "var(--sky-ink)" }}>{iniciales(d.supervisor.nombre)}</div>
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
