import { useState } from "react";
import { useApp } from "../../App.jsx";
import { api } from "../../api.js";
import { Avatar, Barra, Chip, MarcaEstado, Vista, fecha, tonoBarra, useAccion, useApi, useEventos } from "../../ui.jsx";

export default function Equipo() {
  const [seleccion, setSeleccion] = useState(null);
  if (seleccion) return <Detalle id={seleccion} volver={() => setSeleccion(null)} />;
  return <Lista abrir={setSeleccion} />;
}

function Lista({ abrir }) {
  const equipo = useApi("/api/supervisor/equipo");
  useEventos(() => equipo.recargar());
  return (
    <Vista estado={equipo}>
      {(e) => {
        const cols = e.colaboradores;
        const promedio = cols.length ? Math.round(cols.reduce((s, c) => s + c.avance, 0) / cols.length) : 0;
        const escalados = cols.filter((c) => c.escalados.length).length;
        return (
          <>
            <div className="head"><h1>Mi equipo</h1><p className="muted">Colaboradores que Recursos Humanos te asignó para darles seguimiento.</p></div>
            <div className="grid g3">
              <div className="card corner tint-lav stat"><div className="small">Integrantes en onboarding</div><div className="n">{cols.length}</div></div>
              <div className="card tint-peach stat"><div className="small">Con retraso</div><div className="n">{cols.filter((c) => c.estado === "retrasado").length}</div></div>
              <div className="card tint-mint stat"><div className="small">Avance promedio</div><div className="n">{promedio}%</div></div>
            </div>
            {escalados > 0 && (
              <div className="notice rose mt" role="status">
                <b>{escalados === 1 ? "1 colaborador agotó" : `${escalados} colaboradores agotaron`} sus intentos en una evaluación.</b>{" "}
                Ábrelo para revisar sus resultados y, si lo consideras, darle un intento más.
              </div>
            )}
            {cols.length === 0 ? <div className="notice mt">Recursos Humanos aún no te asigna colaboradores.</div> : (
              <div className="card mt"><div className="tablewrap"><table>
                <thead><tr><th>Colaborador</th><th>Área</th><th>Inicio</th><th style={{ width: "26%" }}>Avance</th><th>Estado</th><th>Seguimiento</th></tr></thead>
                <tbody>{cols.map((c) => (
                  <tr key={c.id} className="click" tabIndex={0} onClick={() => abrir(c.id)} onKeyDown={(ev) => ev.key === "Enter" && abrir(c.id)}>
                    <td><b>{c.nombre}</b><div className="small muted">{c.puesto}</div>
                      {c.escalados.map((m) => <span key={m.modulo_id} className="chip bad mt-s">Agotó intentos · {m.modulo}</span>)}</td>
                    <td className="muted">{c.area}</td>
                    <td className="muted">{fecha(c.fecha_ingreso)}</td>
                    <td><div className="row"><Barra valor={c.avance} tono={tonoBarra(c.estado)} /><span className="small">{c.avance}%</span></div></td>
                    <td><Chip estado={c.estado} /></td>
                    <td className="small">{c.comentarios ? `${c.comentarios} nota(s)` : <span className="muted">—</span>}</td>
                  </tr>
                ))}</tbody>
              </table></div></div>
            )}
          </>
        );
      }}
    </Vista>
  );
}

const ACCIONES = [
  ["solicitud", "Solicitar actividad", "Por favor completa tu actividad pendiente esta semana.", ""],
  ["apoyo", "Necesita apoyo", "Detecté que necesitas apoyo; agendemos una sesión.", "ghost"],
  ["seguimiento", "Marcar seguimiento", "Seguimiento realizado.", "mint"],
];
const TIPOS = { comentario: "Comentario", solicitud: "Solicitud", apoyo: "Apoyo", seguimiento: "Seguimiento" };

function Detalle({ id, volver }) {
  const detalle = useApi(`/api/supervisor/colaboradores/${id}`);
  const recomendacion = useApi(`/api/supervisor/colaboradores/${id}/recomendacion`);
  const { config } = useApp();
  const [ejecutar, ocupado] = useAccion();

  const darIntento = async (e) => {
    const ok = await ejecutar(() => api(`/api/supervisor/colaboradores/${id}/modulos/${e.modulo_id}/intento-extra`, { metodo: "POST" }),
      `Se le concedió un intento más en ${e.modulo}`);
    if (ok) detalle.recargar();
  };

  const comentar = async (tipo, texto) => {
    if (await ejecutar(() => api(`/api/supervisor/colaboradores/${id}/comentarios`, { metodo: "POST", datos: { tipo, texto } }), "Registrado; el colaborador lo verá en su inicio")) {
      detalle.recargar();
      return true;
    }
    return false;
  };

  return (
    <>
      <button className="btn ghost sm" onClick={volver}>← Mi equipo</button>
      <Vista estado={detalle}>
        {(c) => (
          <>
            <div className="head mt row wrap" style={{ gap: 16 }}>
              <Avatar u={c} className="avatar lg" />
              <div><h1>{c.nombre}</h1><p className="muted">{c.puesto} · Inicio {fecha(c.fecha_ingreso)} · <Chip estado={c.estado} /></p></div>
            </div>

            <div className="notice peach">
              <b>{config.agentes?.recomendador || "Agente Recomendador"}</b>
              <p className="mt-s">{recomendacion.cargando ? "Analizando su avance…" : recomendacion.error ? recomendacion.error : recomendacion.datos?.recomendacion}</p>
            </div>

            <div className="grid g2 mt">
              <div className="card">
                <div className="row between"><h3>Avance</h3><b>{c.avance}%</b></div>
                <div className="mt-s"><Barra valor={c.avance} tono={tonoBarra(c.estado)} /></div>
                <div className="list mt">{c.modulos.map((m) => (
                  <div key={m.id}>
                    <MarcaEstado estado={m.estado} bloqueado="punto" />
                    <span style={{ flex: 1 }}>{m.titulo}</span>
                    <Chip estado={m.estado === "completado" ? "completado" : m.estado === "en_curso" ? "en_curso" : "pendiente"}>{m.estado === "completado" ? "Completado" : m.estado === "en_curso" ? "En curso" : "Pendiente"}</Chip>
                  </div>
                ))}</div>
              </div>
              <div className="card">
                <h3>Evaluaciones</h3>
                {c.evaluaciones.length === 0 ? <p className="muted small mt-s">Aún no presenta evaluaciones.</p> : (
                  <table className="mt-s"><thead><tr><th>Evaluación</th><th>Resultado</th><th>Intentos</th></tr></thead>
                    <tbody>{c.evaluaciones.map((e) => (
                      <tr key={e.modulo_id}>
                        <td>{e.modulo}</td>
                        <td><Chip estado={e.aprobada ? "validado" : "rechazado"}>{e.calificacion}%</Chip></td>
                        <td>
                          <span className="small">{e.intentos_usados} de {e.intentos_permitidos}</span>
                          {e.intentos_agotados && (
                            <div className="mt-s"><button className="btn ghost sm" disabled={ocupado} onClick={() => darIntento(e)}>Dar un intento más</button></div>
                          )}
                        </td>
                      </tr>
                    ))}</tbody>
                  </table>
                )}
                <h3 className="mt-l">Acciones</h3>
                <div className="row wrap mt-s">
                  {ACCIONES.map(([tipo, etiqueta, texto, tono]) => (
                    <button key={tipo} className={`btn sm ${tono}`} disabled={ocupado} onClick={() => comentar(tipo, texto)}>{etiqueta}</button>
                  ))}
                </div>
              </div>
            </div>

            <div className="card mt">
              <h3>Comentarios y observaciones</h3>
              <form className="row mt" style={{ alignItems: "stretch" }} onSubmit={async (e) => {
                e.preventDefault();
                const form = e.target;
                if (await comentar("comentario", new FormData(form).get("texto"))) form.reset();
              }}>
                <input type="text" name="texto" required minLength={2} placeholder={`Escribe una observación para ${c.nombre.split(" ")[0]}…`} aria-label="Observación" />
                <button className="btn" disabled={ocupado}>Enviar</button>
              </form>
              <div className="list mt">
                {c.comentarios.length === 0 ? <div className="muted small">Sin comentarios todavía.</div> : c.comentarios.map((n) => (
                  <div key={n.id}><Chip estado="revision">{TIPOS[n.tipo] || n.tipo}</Chip><span style={{ flex: 1 }}>{n.texto}</span><span className="small muted">{fecha(n.fecha)}</span></div>
                ))}
              </div>
            </div>
          </>
        )}
      </Vista>
    </>
  );
}
