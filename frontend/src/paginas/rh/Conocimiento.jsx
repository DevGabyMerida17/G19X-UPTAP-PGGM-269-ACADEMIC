import { useState } from "react";
import { api } from "../../api.js";
import { Vista, fecha, useAccion, useApi } from "../../ui.jsx";

export default function Conocimiento() {
  const docs = useApi("/api/rh/conocimiento");
  const [editando, setEditando] = useState(null); // null, "nuevo" o el documento
  const [confirmarBorrar, setConfirmarBorrar] = useState(null);
  const [ejecutar, ocupado] = useAccion();

  const guardar = async (e) => {
    e.preventDefault();
    const datos = Object.fromEntries(new FormData(e.target));
    const nuevo = editando === "nuevo";
    if (!nuevo) datos.modulo_id = editando.modulo_id;
    const ok = await ejecutar(() => api(nuevo ? "/api/rh/conocimiento" : `/api/rh/conocimiento/${editando.id}`,
      { metodo: nuevo ? "POST" : "PUT", datos }), "Guardado. El Tutor IA ya usa esta versión.");
    if (ok) { setEditando(null); docs.recargar(); }
  };
  const borrar = async (d) => {
    if (await ejecutar(() => api(`/api/rh/conocimiento/${d.id}`, { metodo: "DELETE" }), "Documento eliminado")) {
      setConfirmarBorrar(null); docs.recargar();
    }
  };
  const subirTexto = async (e, form) => {
    const archivo = e.target.files[0];
    if (!archivo) return;
    form.elements.contenido.value = await archivo.text();
    if (!form.elements.titulo.value) form.elements.titulo.value = archivo.name.replace(/\.(md|txt)$/i, "");
  };

  return (
    <>
      <div className="head row between wrap">
        <div><h1>Base de conocimiento del Tutor IA</h1><p className="muted">Documentos de la empresa con los que el Tutor responde. Reemplaza los de ejemplo con la información oficial.</p></div>
        {!editando && <button className="btn" onClick={() => setEditando("nuevo")}>+ Agregar documento</button>}
      </div>

      {editando && (
        <form className="card corner tint-lav" onSubmit={guardar} style={{ marginBottom: 16 }}>
          <h3>{editando === "nuevo" ? "Nuevo documento" : `Editar: ${editando.titulo}`}</h3>
          <div className="grid g2 mt">
            <label className="field">Título<input type="text" name="titulo" required minLength={3} defaultValue={editando.titulo || ""} /></label>
            <label className="field">Tema (para las métricas)<input type="text" name="tema" placeholder="Ej. Vacaciones" defaultValue={editando.tema || ""} /></label>
          </div>
          <label className="field mt">Contenido
            <textarea name="contenido" required minLength={10} style={{ minHeight: 240 }} defaultValue={editando.contenido || ""}
              placeholder={"## Sección\nTexto que el Tutor podrá citar…"} />
            <span className="hint">Divide el texto en secciones que empiecen con "## ". El Tutor cita la sección que usó.</span>
          </label>
          <label className="btn ghost sm mt">Cargar desde archivo .md o .txt
            <input type="file" accept=".md,.txt" hidden onChange={(e) => subirTexto(e, e.target.form)} />
          </label>
          <div className="row mt"><button className="btn" disabled={ocupado}>Guardar</button><button type="button" className="btn ghost" onClick={() => setEditando(null)}>Cancelar</button></div>
        </form>
      )}

      <Vista estado={docs}>
        {(lista) => (
          <div className="card list">
            {lista.map((d) => (
              <div key={d.id} style={{ flexWrap: "wrap" }}>
                <div style={{ flex: 1, minWidth: 220 }}>
                  <b>{d.titulo}</b>
                  <div className="small muted">{d.tema || "Sin tema"} · {(d.contenido.match(/^## /gm) || []).length || 1} secciones{d.modulo_id ? " · contenido de un módulo" : ""} · actualizado {fecha(d.actualizado_en)}</div>
                </div>
                <button className="btn ghost sm" onClick={() => { setEditando(d); window.scrollTo(0, 0); }}>Editar</button>
                {confirmarBorrar === d.id
                  ? <><button className="btn rose sm" disabled={ocupado} onClick={() => borrar(d)}>Sí, eliminar</button><button className="btn ghost sm" onClick={() => setConfirmarBorrar(null)}>No</button></>
                  : <button className="btn ghost sm" onClick={() => setConfirmarBorrar(d.id)}>Eliminar</button>}
              </div>
            ))}
          </div>
        )}
      </Vista>
    </>
  );
}
