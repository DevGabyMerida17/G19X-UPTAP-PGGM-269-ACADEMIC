import { useState } from "react";
import { api } from "../../api.js";
import { Vista, useAccion, useApi } from "../../ui.jsx";

const LETRAS = "ABCDEF";

export default function Actividades() {
  const preguntas = useApi("/api/rh/preguntas");
  const modulos = useApi("/api/rh/modulos");
  const [opciones, setOpciones] = useState(["", "", ""]);
  const [ejecutar, ocupado] = useAccion();

  const guardar = async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    const datos = {
      modulo_id: Number(f.get("modulo_id")), texto: f.get("texto"), opciones: opciones.map((o) => o.trim()),
      correcta: Number(f.get("correcta")), retroalimentacion: f.get("retroalimentacion"),
    };
    if (await ejecutar(() => api("/api/rh/preguntas", { metodo: "POST", datos }), "Pregunta guardada")) {
      e.target.reset(); setOpciones(["", "", ""]); preguntas.recargar(); modulos.recargar();
    }
  };
  const minimo = async (m, valor) => {
    const n = Number(valor);
    if (Number.isNaN(n) || n < 0 || n > 100 || n === m.puntuacion_minima) return;
    await ejecutar(() => api(`/api/rh/modulos/${m.id}`, { metodo: "PATCH", datos: { puntuacion_minima: n } }), "Puntuación mínima actualizada");
    modulos.recargar(); preguntas.recargar();
  };
  const intentosMax = async (m, valor) => {
    const n = Number(valor);
    if (!Number.isInteger(n) || n < 1 || n > 10 || n === m.intentos_maximos) return;
    await ejecutar(() => api(`/api/rh/modulos/${m.id}`, { metodo: "PATCH", datos: { intentos_maximos: n } }), "Intentos actualizados");
    modulos.recargar();
  };
  const borrar = async (p) => { await ejecutar(() => api(`/api/rh/preguntas/${p.id}`, { metodo: "DELETE" }), "Pregunta eliminada"); preguntas.recargar(); modulos.recargar(); };

  return (
    <>
      <div className="head"><h1>Actividades y evaluaciones</h1><p className="muted">Crea preguntas, define la respuesta correcta y la puntuación mínima de cada módulo.</p></div>

      <form className="card corner tint-sky" onSubmit={guardar}>
        <h3>Nueva pregunta</h3>
        <label className="field mt">Pregunta<input type="text" name="texto" required minLength={5} /></label>
        <div className="grid g3 mt">
          {opciones.map((o, i) => (
            <label key={i} className="field">Opción {LETRAS[i]}
              <input type="text" value={o} required onChange={(e) => setOpciones(opciones.map((x, j) => (j === i ? e.target.value : x)))} />
            </label>
          ))}
        </div>
        <div className="row mt wrap">
          {opciones.length < 6 && <button type="button" className="btn ghost sm" onClick={() => setOpciones([...opciones, ""])}>+ Opción</button>}
          {opciones.length > 2 && <button type="button" className="btn ghost sm" onClick={() => setOpciones(opciones.slice(0, -1))}>− Opción</button>}
        </div>
        <div className="grid g2 mt">
          <label className="field">Respuesta correcta<select name="correcta">{opciones.map((_, i) => <option key={i} value={i}>Opción {LETRAS[i]}</option>)}</select></label>
          <label className="field">Módulo<select name="modulo_id">{(modulos.datos || []).map((m) => <option key={m.id} value={m.id}>{m.titulo}</option>)}</select></label>
        </div>
        <label className="field mt">Retroalimentación si se equivoca<input type="text" name="retroalimentacion" placeholder="Explica por qué la respuesta correcta lo es" /></label>
        <button className="btn mt" disabled={ocupado}>Guardar pregunta</button>
      </form>

      <Vista estado={modulos}>
        {(ms) => {
          const conPreguntas = ms.filter((m) => m.preguntas > 0);
          return conPreguntas.length > 0 && (
            <div className="card mt"><h3>Reglas de cada evaluación</h3>
              <p className="small muted mt-s">Si alguien agota sus intentos, su responsable o RH pueden concederle uno más.</p>
              <div className="list mt-s">{conPreguntas.map((m) => (
                <div key={m.id} style={{ flexWrap: "wrap" }}>
                  <span style={{ flex: 1, minWidth: 180 }}>{m.titulo} <span className="small muted">· {m.preguntas} preguntas</span></span>
                  <label className="row small">Mínimo
                    <input type="number" min={0} max={100} defaultValue={m.puntuacion_minima} style={{ width: 80 }} onBlur={(e) => minimo(m, e.target.value)} aria-label={`Puntuación mínima de ${m.titulo}`} />%
                  </label>
                  <label className="row small">Intentos
                    <input type="number" min={1} max={10} defaultValue={m.intentos_maximos} style={{ width: 70 }} onBlur={(e) => intentosMax(m, e.target.value)} aria-label={`Intentos permitidos en ${m.titulo}`} />
                  </label>
                </div>
              ))}</div>
            </div>
          );
        }}
      </Vista>

      <Vista estado={preguntas}>
        {(ps) => (
          <div className="card mt"><h3>Preguntas registradas</h3>
            <div className="tablewrap mt-s"><table>
              <thead><tr><th>Pregunta</th><th>Respuesta correcta</th><th>Módulo</th><th></th></tr></thead>
              <tbody>{ps.map((p) => (
                <tr key={p.id}><td>{p.texto}</td><td className="small">{p.opciones[p.correcta]}</td><td className="muted">{p.modulo}</td>
                  <td><button className="btn ghost sm" disabled={ocupado} onClick={() => borrar(p)}>Eliminar</button></td></tr>
              ))}</tbody>
            </table></div>
          </div>
        )}
      </Vista>
    </>
  );
}
