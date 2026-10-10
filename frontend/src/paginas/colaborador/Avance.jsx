import { useResumen } from "../../App.jsx";
import { Chip, MarcaEstado, Vista } from "../../ui.jsx";

export default function Avance() {
  const resumen = useResumen();
  return (
    <Vista estado={resumen}>
      {(d) => {
        const hechos = d.modulos.filter((m) => m.estado === "completado");
        const pendientes = d.modulos.filter((m) => m.estado !== "completado");
        const proximas = d.tareas.filter((t) => !t.hecha).slice(0, 5);
        const promedio = d.evaluaciones.length
          ? Math.round(d.evaluaciones.reduce((s, e) => s + e.calificacion, 0) / d.evaluaciones.length) : null;
        return (
          <>
            <div className="head"><h1>Mi avance</h1></div>
            <div className="grid g3">
              <div className="card corner tint-lav stat"><div className="small">Avance general</div><div className="n">{d.avance}%</div></div>
              <div className="card tint-mint stat"><div className="small">Módulos completados</div><div className="n">{hechos.length}/{d.modulos.length}</div></div>
              <div className="card tint-sky stat"><div className="small">Calificación promedio</div><div className="n">{promedio === null ? "—" : `${promedio}%`}</div></div>
            </div>
            <div className="grid g2 mt">
              <div className="card"><h3>Completados</h3><div className="list mt-s">
                {hechos.length ? hechos.map((m) => <div key={m.id}><MarcaEstado estado="completado" />{m.titulo}</div>) : <div className="muted">Aún ninguno</div>}
              </div></div>
              <div className="card"><h3>Pendientes</h3><div className="list mt-s">
                {pendientes.length ? pendientes.map((m) => <div key={m.id}><MarcaEstado estado={m.estado} bloqueado="punto" />{m.titulo}</div>) : <div className="muted">¡Nada pendiente!</div>}
              </div></div>
            </div>
            <div className="card mt"><h3>Calificaciones</h3>
              {d.evaluaciones.length === 0 ? <p className="muted small mt-s">Todavía no presentas evaluaciones.</p> : (
                <div className="tablewrap"><table className="mt-s"><thead><tr><th>Evaluación</th><th>Mínimo</th><th>Mejor resultado</th></tr></thead>
                  <tbody>{d.evaluaciones.map((e) => (
                    <tr key={e.modulo_id}><td>{e.modulo}</td><td>{e.minimo}%</td><td><Chip estado={e.aprobada ? "validado" : "rechazado"}>{e.calificacion}%</Chip></td></tr>
                  ))}</tbody></table></div>
              )}
            </div>
            <div className="card mt"><h3>Próximas actividades</h3><div className="list mt-s">
              {proximas.length ? proximas.map((t) => <div key={t.id}><Chip estado="en_curso">{t.etapa}</Chip>{t.titulo}</div>) : <div className="muted">No hay actividades pendientes</div>}
            </div></div>
          </>
        );
      }}
    </Vista>
  );
}
