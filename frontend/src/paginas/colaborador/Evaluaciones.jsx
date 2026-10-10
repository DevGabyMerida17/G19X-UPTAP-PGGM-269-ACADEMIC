import { useEffect, useState } from "react";
import { useResumen } from "../../App.jsx";
import { api } from "../../api.js";
import { Chip, Vista, useAccion, useApi } from "../../ui.jsx";

export default function Evaluaciones({ ir, params }) {
  const resumen = useResumen();
  const [abierta, setAbierta] = useState(params.modulo || null);
  useEffect(() => { setAbierta(params.modulo || null); }, [params.modulo]);
  if (abierta) return <Examen id={abierta} volver={() => setAbierta(null)} />;

  return (
    <Vista estado={resumen}>
      {(d) => {
        const conEval = d.modulos.filter((m) => m.tiene_evaluacion);
        return (
          <>
            <div className="head"><h1>Evaluaciones</h1><p className="muted">Se habilitan al terminar de leer cada módulo.</p></div>
            {conEval.length === 0 && <div className="notice">Tu programa no tiene evaluaciones por ahora.</div>}
            <div className="stack">
              {conEval.map((m) => {
                const nota = d.evaluaciones.find((e) => e.modulo_id === m.id);
                const lista = m.estado !== "bloqueado" && m.leidas >= m.total;
                return (
                  <div key={m.id} className="card row between wrap">
                    <div>
                      <h3>{m.titulo}</h3>
                      <p className="small muted mt-s">Mínimo para aprobar: {m.puntuacion_minima}%</p>
                    </div>
                    <div className="row">
                      {nota && <Chip estado={nota.aprobada ? "validado" : "rechazado"}>Mejor calificación: {nota.calificacion}%</Chip>}
                      {lista
                        ? <button className="btn sm" onClick={() => setAbierta(m.id)}>{nota ? "Presentar de nuevo" : "Presentar"}</button>
                        : <button className="btn ghost sm" onClick={() => ir("capacitacion", { modulo: m.estado === "bloqueado" ? undefined : m.id })}>{m.estado === "bloqueado" ? "Bloqueada" : "Terminar de leer"}</button>}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        );
      }}
    </Vista>
  );
}

function Examen({ id, volver }) {
  const examen = useApi(`/api/yo/modulos/${id}/evaluacion`);
  const resumen = useResumen();
  const [respuestas, setRespuestas] = useState({});
  const [resultado, setResultado] = useState(null);
  const [ejecutar, ocupado] = useAccion();

  const enviar = async (preguntas) => {
    if (preguntas.some((p) => respuestas[p.id] === undefined)) {
      await ejecutar(() => Promise.reject(new Error("Responde todas las preguntas.")));
      return;
    }
    const r = await ejecutar(() => api(`/api/yo/modulos/${id}/evaluacion`, { metodo: "POST", datos: { respuestas } }));
    if (r) { setResultado(r); resumen.recargar(); window.scrollTo(0, 0); }
  };
  const reintentar = () => { setResultado(null); setRespuestas({}); };

  return (
    <>
      <button className="btn ghost sm" onClick={volver}>← Evaluaciones</button>
      <Vista estado={examen}>
        {(ex) => {
          const porPregunta = Object.fromEntries((resultado?.resultado || []).map((r) => [r.pregunta_id, r]));
          return (
            <>
              <div className="head mt"><h1>Evaluación: {ex.modulo}</h1><p className="muted">{ex.preguntas.length} preguntas · calificación mínima {ex.minimo}%</p></div>
              {!ex.disponible && <div className="notice">Termina de leer el módulo para presentar esta evaluación.</div>}
              {resultado && (
                <div className={`card row between wrap ${resultado.aprobada ? "tint-mint" : "tint-peach"}`}>
                  <div><div className="small">Tu calificación</div><div className="stat"><div className="n">{resultado.calificacion}%</div></div></div>
                  <div>{resultado.aprobada
                    ? <><b>¡Aprobada!</b><div className="small">El módulo quedó completado.</div></>
                    : <><b>Aún no alcanzas el mínimo</b><div className="small">Revisa la retroalimentación e inténtalo de nuevo.</div></>}</div>
                  {!resultado.aprobada && <button className="btn" onClick={reintentar}>Reintentar</button>}
                </div>
              )}
              {ex.disponible && (
                <div className="card mt">
                  {ex.preguntas.map((p, qi) => {
                    const r = porPregunta[p.id];
                    return (
                      <fieldset key={p.id} className="q" style={{ border: 0, margin: 0 }}>
                        <legend style={{ fontWeight: 700, padding: 0 }}>{qi + 1}. {p.texto}</legend>
                        {p.opciones.map((o, oi) => {
                          const cls = r ? (oi === r.correcta ? "right" : r.elegida === oi ? "wrong" : "") : "";
                          return (
                            <label key={oi} className={`opt ${cls}`}>
                              <input type="radio" name={`p${p.id}`} disabled={!!resultado} checked={respuestas[p.id] === oi}
                                onChange={() => setRespuestas({ ...respuestas, [p.id]: oi })} />
                              {o}
                            </label>
                          );
                        })}
                        {r && !r.acierto && r.retroalimentacion && <div className="notice mt-s small"><b>Retroalimentación:</b> {r.retroalimentacion}</div>}
                      </fieldset>
                    );
                  })}
                  {!resultado && <button className="btn mt" onClick={() => enviar(ex.preguntas)} disabled={ocupado}>Enviar respuestas</button>}
                </div>
              )}
            </>
          );
        }}
      </Vista>
    </>
  );
}
