import { useEffect, useState } from "react";
import { ClipboardCheck, Lightbulb, RotateCcw } from "lucide-react";
import { useApp, useResumen } from "../../App.jsx";
import { api } from "../../api.js";
import { Chip, Vista, useAccion, useApi } from "../../ui.jsx";

export default function Evaluaciones({ ir, params }) {
  const resumen = useResumen();
  const { config } = useApp();
  const [abierta, setAbierta] = useState(params.modulo || null);
  useEffect(() => { setAbierta(params.modulo || null); }, [params.modulo]);
  if (abierta) return <Examen id={abierta} volver={() => setAbierta(null)} />;

  return (
    <Vista estado={resumen}>
      {(d) => {
        const conEval = d.modulos.filter((m) => m.tiene_evaluacion);
        return (
          <>
            <div className="head"><h1>Evaluaciones</h1><p className="muted">Se habilitan al terminar de leer cada módulo. Al terminar, el {config.agentes?.evaluador || "Agente Evaluador"} te explica tus errores y qué reforzar.</p></div>
            {conEval.length === 0 && <div className="notice">Tu programa no tiene evaluaciones por ahora.</div>}
            <div className="stack">
              {conEval.map((m) => {
                const nota = d.evaluaciones.find((e) => e.modulo_id === m.id);
                const lista = m.estado !== "bloqueado" && m.leidas >= m.total;
                const aprobada = nota?.aprobada;
                const agotados = nota?.intentos_agotados;
                return (
                  <div key={m.id} className="card row between wrap">
                    <div>
                      <h3>{m.titulo}</h3>
                      <p className="small muted mt-s">
                        Mínimo para aprobar: {m.puntuacion_minima}%
                        {nota && ` · Intentos: ${nota.intentos_usados} de ${nota.intentos_permitidos}`}
                      </p>
                    </div>
                    <div className="row wrap">
                      {nota && <Chip estado={aprobada ? "validado" : "rechazado"}>Mejor calificación: {nota.calificacion}%</Chip>}
                      {aprobada ? (
                        <button className="btn ghost sm" onClick={() => setAbierta(m.id)}>Ver resultado</button>
                      ) : agotados ? (
                        <Chip estado="inactivo">Sin intentos</Chip>
                      ) : lista ? (
                        <button className="btn sm" onClick={() => setAbierta(m.id)}>{nota ? "Presentar de nuevo" : "Presentar"}</button>
                      ) : (
                        <button className="btn ghost sm" onClick={() => ir("capacitacion", { modulo: m.estado === "bloqueado" ? undefined : m.id })}>
                          {m.estado === "bloqueado" ? "Bloqueada" : "Terminar de leer"}
                        </button>
                      )}
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
    if (r) { setResultado(r); resumen.recargar(); examen.recargar(); window.scrollTo(0, 0); }
  };
  const reintentar = () => { setResultado(null); setRespuestas({}); window.scrollTo(0, 0); };

  return (
    <>
      <button className="btn ghost sm" onClick={volver}>← Evaluaciones</button>
      <Vista estado={examen}>
        {(ex) => {
          const it = resultado?.intentos || ex.intentos;
          const porPregunta = Object.fromEntries((resultado?.resultado || []).map((r) => [r.pregunta_id, r]));
          const bloqueada = !resultado && (ex.intentos.aprobada || ex.intentos.agotados);
          return (
            <>
              <div className="head mt">
                <h1>Evaluación: {ex.modulo}</h1>
                <p className="muted">
                  {ex.preguntas.length} preguntas · calificación mínima {ex.minimo}% · intento {Math.min(it.usados + (resultado ? 0 : 1), it.permitidos)} de {it.permitidos}
                </p>
              </div>

              {!ex.disponible && <div className="notice">Termina de leer el módulo para presentar esta evaluación.</div>}
              {bloqueada && ex.intentos.aprobada && <div className="notice mint">Ya aprobaste esta evaluación. ¡Bien hecho!</div>}
              {bloqueada && ex.intentos.agotados && (
                <div className="notice rose">
                  <b>Ya usaste tus {ex.intentos.permitidos} intentos.</b>
                  <p className="mt-s">Tu responsable o Recursos Humanos pueden concederte otro. Mientras tanto, repasa el módulo; el Agente Recomendador te sugiere qué reforzar en tu Inicio.</p>
                </div>
              )}

              {resultado && (
                <>
                  <div className={`card row between wrap ${resultado.aprobada ? "tint-mint" : "tint-peach"}`}>
                    <div><div className="small">Tu calificación</div><div className="stat"><div className="n">{resultado.calificacion}%</div></div></div>
                    <div>{resultado.aprobada
                      ? <><b>¡Aprobada!</b><div className="small">El módulo quedó completado.</div></>
                      : <><b>Aún no alcanzas el mínimo</b>
                          <div className="small">{resultado.intentos.restantes > 0
                            ? `Te quedan ${resultado.intentos.restantes} intento(s). Revisa la retroalimentación antes de volver a intentarlo.`
                            : "Ya no te quedan intentos. Tu responsable o RH pueden concederte otro."}</div></>}
                    </div>
                    {!resultado.aprobada && resultado.intentos.restantes > 0 && (
                      <button className="btn" onClick={reintentar}><RotateCcw size={16} strokeWidth={1.8} />Reintentar</button>
                    )}
                  </div>
                  <RetroEvaluador evaluacionId={resultado.evaluacion_id} preguntas={ex.preguntas} />
                </>
              )}

              {ex.disponible && !bloqueada && (
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

/** Retroalimentación del Agente Evaluador: se pide después de calificar porque puede tardar unos segundos. */
function RetroEvaluador({ evaluacionId, preguntas }) {
  const { config } = useApp();
  const [retro, setRetro] = useState(null);
  const [error, setError] = useState("");
  const [intento, setIntento] = useState(0);

  useEffect(() => {
    let cancelado = false;
    setRetro(null); setError("");
    api(`/api/yo/evaluaciones/${evaluacionId}/retroalimentacion`, { metodo: "POST" })
      .then((r) => !cancelado && setRetro(r))
      .catch((e) => !cancelado && setError(e.message));
    return () => { cancelado = true; };
  }, [evaluacionId, intento]);

  return (
    <div className="card mt agente-card" aria-live="polite">
      <div className="row"><span className="agente-ico"><ClipboardCheck size={18} strokeWidth={1.8} /></span><h3>{config.agentes?.evaluador || "Agente Evaluador"}</h3></div>
      {!retro && !error && <p className="muted mt-s">Revisando tus respuestas…</p>}
      {error && (
        <div className="mt-s">
          <p className="muted">{error}</p>
          <button className="btn ghost sm mt-s" onClick={() => setIntento(intento + 1)}>Volver a intentar</button>
        </div>
      )}
      {retro && (
        <>
          <p className="mt-s">{retro.resumen}</p>
          {retro.errores?.length > 0 && (
            <div className="stack mt">
              {retro.errores.map((e) => (
                <div key={e.numero} className="retro-error">
                  <b>Pregunta {e.numero}{preguntas[e.numero - 1] ? `: ${preguntas[e.numero - 1].texto}` : ""}</b>
                  <p className="small mt-s">{e.explicacion}</p>
                </div>
              ))}
            </div>
          )}
          {retro.temas_a_reforzar?.length > 0 && (
            <div className="mt">
              <div className="small muted">Temas a reforzar</div>
              <div className="row wrap mt-s" style={{ gap: 8 }}>{retro.temas_a_reforzar.map((t) => <span key={t} className="chip wait">{t}</span>)}</div>
            </div>
          )}
          {retro.siguiente_paso && <p className="small mt row" style={{ gap: 8 }}><Lightbulb size={16} strokeWidth={1.8} />{retro.siguiente_paso}</p>}
        </>
      )}
    </div>
  );
}
