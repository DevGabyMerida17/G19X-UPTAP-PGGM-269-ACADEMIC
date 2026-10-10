import { useState } from "react";
import { api } from "../../api.js";
import { Chip, Vista, useAccion, useApi } from "../../ui.jsx";

const TONOS = ["tint-lav", "tint-mint", "tint-peach", "tint-sky", "tint-butter"];

export default function Programas() {
  const programas = useApi("/api/rh/programas");
  const modulos = useApi("/api/rh/modulos");
  const [nuevoModulo, setNuevoModulo] = useState(false);
  const [ejecutar, ocupado] = useAccion();
  const recargar = () => { programas.recargar(); modulos.recargar(); };

  const crearPrograma = async (e) => {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.target));
    if (await ejecutar(() => api("/api/rh/programas", { metodo: "POST", datos: f }), "Programa creado")) { e.target.reset(); recargar(); }
  };
  const crearModulo = async (e) => {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.target));
    const datos = { ...f, programa_id: Number(f.programa_id), minutos: Number(f.minutos) };
    if (await ejecutar(() => api("/api/rh/modulos", { metodo: "POST", datos }), "Módulo creado. Su contenido ya lo usa el Tutor IA.")) {
      setNuevoModulo(false); recargar();
    }
  };
  const editar = async (m, datos) => { await ejecutar(() => api(`/api/rh/modulos/${m.id}`, { metodo: "PATCH", datos })); recargar(); };
  const mover = async (m, dir) => { await ejecutar(() => api(`/api/rh/modulos/${m.id}/mover/${dir}`, { metodo: "POST" })); modulos.recargar(); };

  return (
    <>
      <div className="head"><h1>Programas y módulos</h1><p className="muted">Crea programas, ordena sus módulos y actívalos o desactívalos.</p></div>
      <Vista estado={programas}>
        {(ps) => (
          <div className="grid g3">
            {ps.map((p, i) => (
              <div key={p.id} className={`card ${TONOS[i % TONOS.length]} ${i === 0 ? "corner" : ""}`}>
                <h3>{p.titulo}</h3><p className="small mt-s">{p.descripcion || "Sin descripción"}</p>
                <div className="row mt small wrap"><Chip estado="en_curso">{p.modulos} módulos</Chip><Chip estado="validado">{p.colaboradores} colaboradores</Chip></div>
              </div>
            ))}
          </div>
        )}
      </Vista>

      <form className="card mt row wrap" onSubmit={crearPrograma} style={{ alignItems: "flex-end" }}>
        <label className="field" style={{ flex: 1, minWidth: 200 }}>Nuevo programa<input type="text" name="titulo" placeholder="Ej. Onboarding Ventas" required minLength={3} /></label>
        <label className="field" style={{ flex: 2, minWidth: 200 }}>Descripción<input type="text" name="descripcion" /></label>
        <button className="btn" disabled={ocupado}>Crear programa</button>
      </form>

      <div className="card mt">
        <div className="row between wrap"><h3>Módulos</h3>{!nuevoModulo && <button className="btn sm" onClick={() => setNuevoModulo(true)}>+ Nuevo módulo</button>}</div>
        {nuevoModulo && (
          <form className="card tint-sky mt" onSubmit={crearModulo}>
            <div className="grid g3">
              <label className="field">Título<input type="text" name="titulo" required minLength={3} /></label>
              <label className="field">Programa<select name="programa_id">{(programas.datos || []).map((p) => <option key={p.id} value={p.id}>{p.titulo}</option>)}</select></label>
              <label className="field">Minutos<input type="number" name="minutos" min={1} max={600} defaultValue={10} /></label>
            </div>
            <label className="field mt">Contenido
              <textarea name="contenido" required minLength={10} placeholder={"## Primera sección\nTexto de la sección…\n\n## Segunda sección\nMás texto…"} />
              <span className="hint">Empieza cada sección con "## " y su título.</span>
            </label>
            <div className="row mt"><button className="btn" disabled={ocupado}>Guardar módulo</button><button type="button" className="btn ghost" onClick={() => setNuevoModulo(false)}>Cancelar</button></div>
          </form>
        )}
        <Vista estado={modulos}>
          {(ms) => (
            <div className="tablewrap mt-s"><table>
              <thead><tr><th>Orden</th><th>Módulo</th><th>Programa</th><th>Evaluación</th><th>Estado</th><th></th></tr></thead>
              <tbody>{ms.map((m, i) => {
                const mismo = (j) => ms[j]?.programa_id === m.programa_id;
                return (
                  <tr key={m.id}>
                    <td><div className="row" style={{ gap: 4 }}>
                      <button className="btn ghost sm" disabled={!mismo(i - 1) || ocupado} onClick={() => mover(m, "arriba")} aria-label={`Subir ${m.titulo}`}>↑</button>
                      <button className="btn ghost sm" disabled={!mismo(i + 1) || ocupado} onClick={() => mover(m, "abajo")} aria-label={`Bajar ${m.titulo}`}>↓</button>
                    </div></td>
                    <td><b>{m.titulo}</b><div className="small muted">{m.secciones} secciones · {m.minutos} min</div></td>
                    <td className="muted">{m.programa}</td>
                    <td className="small">{m.preguntas ? `${m.preguntas} preguntas · mín. ${m.puntuacion_minima}%` : "—"}</td>
                    <td><Chip estado={m.activo ? "validado" : "inactivo"}>{m.activo ? "Activo" : "Inactivo"}</Chip></td>
                    <td><button className="btn ghost sm" disabled={ocupado} onClick={() => editar(m, { activo: !m.activo })}>{m.activo ? "Desactivar" : "Activar"}</button></td>
                  </tr>
                );
              })}</tbody>
            </table></div>
          )}
        </Vista>
      </div>
    </>
  );
}
