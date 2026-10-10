import { useEffect, useState } from "react";
import { useResumen } from "../../App.jsx";
import { api } from "../../api.js";
import { Barra, Chip, MarcaEstado, Vista, useAccion, useApi } from "../../ui.jsx";

export default function Capacitacion({ ir, params }) {
  const [abierto, setAbierto] = useState(params.modulo || null);
  useEffect(() => { setAbierto(params.modulo || null); }, [params.modulo]);
  if (abierto) return <Modulo id={abierto} volver={() => setAbierto(null)} ir={ir} />;
  return <Lista abrir={setAbierto} />;
}

function Lista({ abrir }) {
  const resumen = useResumen();
  return (
    <Vista estado={resumen}>
      {(d) => (
        <>
          <div className="head">
            <h1>Capacitación</h1>
            <p className="muted">{d.programa || "Sin programa asignado"} · {d.modulos.filter((m) => m.estado === "completado").length} de {d.modulos.length} módulos completados</p>
          </div>
          {d.modulos.length === 0 ? <div className="notice">Recursos Humanos aún no te asigna módulos.</div> : (
            <div className="card list">
              {d.modulos.map((m) => (
                <div key={m.id}>
                  <MarcaEstado estado={m.estado} />
                  <div style={{ flex: 1 }}>
                    <b className={m.estado === "bloqueado" ? "muted" : ""}>{m.titulo}</b>
                    {m.tiene_evaluacion && <div className="small muted">Incluye evaluación (mínimo {m.puntuacion_minima}%)</div>}
                  </div>
                  <span className="small muted">{m.minutos} min</span>
                  {m.estado === "bloqueado"
                    ? <Chip estado="bloqueado" />
                    : <button className={`btn sm ${m.estado === "completado" ? "ghost" : ""}`} onClick={() => abrir(m.id)}>{m.estado === "completado" ? "Repasar" : "Abrir"}</button>}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </Vista>
  );
}

function Modulo({ id, volver, ir }) {
  const modulo = useApi(`/api/yo/modulos/${id}`);
  const resumen = useResumen();
  const [ejecutar, ocupado] = useAccion();

  const leer = async () => {
    await ejecutar(() => api(`/api/yo/modulos/${id}/leer`, { metodo: "POST" }));
    modulo.recargar();
    resumen.recargar();
  };
  const completar = async () => {
    const ok = await ejecutar(() => api(`/api/yo/modulos/${id}/completar`, { metodo: "POST" }), "¡Módulo completado!");
    if (ok) { resumen.recargar(); volver(); }
  };

  return (
    <>
      <button className="btn ghost sm" onClick={volver}>← Todos los módulos</button>
      <Vista estado={modulo}>
        {(m) => {
          const completo = m.estado === "completado";
          const leidas = m.leidas;
          return (
            <>
              <div className="head mt">
                <h1>{m.titulo}</h1>
                <p className="muted">{m.minutos} min · {leidas} de {m.total} secciones leídas</p>
                <div className="mt-s" style={{ maxWidth: 380 }}><Barra valor={m.total ? leidas / m.total * 100 : 0} /></div>
              </div>
              <div className="stack">
                {m.secciones.map((s, i) => (
                  <div key={i} className="card" style={i < leidas ? { borderLeft: "4px solid var(--mint-borde)" } : undefined}>
                    <div className="row between"><h3>{i + 1}. {s.titulo}</h3>{i < leidas && <Chip estado="validado">Leído</Chip>}</div>
                    <p className="mt-s">{s.contenido}</p>
                    {i === leidas && !completo && <button className="btn sm mt" onClick={leer} disabled={ocupado}>Marcar como leído</button>}
                  </div>
                ))}
              </div>
              <div className="row mt wrap">
                {!completo && leidas >= m.total && (m.tiene_evaluacion
                  ? <button className="btn mint" onClick={() => ir("evaluaciones", { modulo: m.id })}>Ir a la evaluación</button>
                  : <button className="btn mint" onClick={completar} disabled={ocupado}>Completar módulo</button>)}
                <button className="btn ghost" onClick={() => ir("tutor")}>Preguntar al Tutor sobre este tema</button>
              </div>
            </>
          );
        }}
      </Vista>
    </>
  );
}
