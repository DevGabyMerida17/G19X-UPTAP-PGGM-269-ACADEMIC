import { useState } from "react";
import { useApp } from "../../App.jsx";
import { Barra, Chip, Vista, fecha, tonoBarra, useApi, useEventos } from "../../ui.jsx";

export default function Panel() {
  const panel = useApi("/api/rh/panel");
  const { config } = useApp();
  const [busca, setBusca] = useState("");
  const [area, setArea] = useState("Todas");
  useEventos(() => panel.recargar());

  return (
    <Vista estado={panel}>
      {(p) => {
        const max = Math.max(1, ...p.temas.map((t) => t.consultas));
        const q = busca.trim().toLowerCase();
        const filas = p.procesos.filter((c) => (area === "Todas" || c.area === area) &&
          [c.nombre, c.puesto, c.supervisor].some((x) => (x || "").toLowerCase().includes(q)));
        return (
          <>
            <div className="head"><h1>Panel de onboarding</h1><p className="muted">Se actualiza en tiempo real cuando los colaboradores avanzan.</p></div>
            <div className="grid g4">
              <div className="card corner stat tint-lav"><div className="small">Procesos activos</div><div className="n">{p.procesos_activos}</div></div>
              <div className="card stat tint-mint"><div className="small">Onboardings completados</div><div className="n">{p.completados}</div></div>
              <div className="card stat tint-butter"><div className="small">Documentos por revisar</div><div className="n">{p.documentos_por_revisar}</div></div>
              <div className="card stat tint-peach"><div className="small">Alertas de retraso</div><div className="n" style={{ color: "var(--rose-ink)" }}>{p.alertas_retraso}</div></div>
            </div>

            <div className="card mt">
              <div className="row between wrap">
                <h3>Procesos de onboarding</h3>
                <input type="search" placeholder="Buscar colaborador o responsable" value={busca} onChange={(e) => setBusca(e.target.value)} style={{ maxWidth: 280 }} aria-label="Buscar colaborador" />
              </div>
              <div className="chips-area mt" role="group" aria-label="Filtrar por área">
                {["Todas", ...config.areas].map((a) => (
                  <button key={a} className={area === a ? "on" : ""} aria-pressed={area === a} onClick={() => setArea(a)}>{a}</button>
                ))}
              </div>
              <div className="tablewrap mt-s">
                <table>
                  <thead><tr><th>Colaborador</th><th>Área</th><th>Responsable</th><th>Inicio</th><th style={{ width: "22%" }}>Progreso</th><th>Estado</th></tr></thead>
                  <tbody>
                    {filas.map((c) => (
                      <tr key={c.id}>
                        <td><b>{c.nombre}</b><div className="small muted">{c.puesto}</div></td><td className="muted">{c.area}</td>
                        <td>{c.supervisor || <span className="small" style={{ color: "var(--rose-ink)" }}>Sin asignar</span>}</td>
                        <td className="muted">{fecha(c.fecha_ingreso)}</td>
                        <td><div className="row"><Barra valor={c.avance} tono={tonoBarra(c.estado)} /><span className="small">{c.avance}%</span></div></td>
                        <td><Chip estado={c.estado} /></td>
                      </tr>
                    ))}
                    {!filas.length && <tr><td colSpan={6} className="muted">Sin resultados.</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="grid g2 mt">
              <div className="card">
                <h3>Temas más consultados al Tutor</h3>
                {p.temas.length === 0 ? <p className="muted small mt-s">Aún no hay consultas al Tutor IA.</p> : (
                  <div className="mt">{p.temas.map((t) => (
                    <div key={t.tema} className="hbar"><span>{t.tema}</span><Barra valor={t.consultas / max * 100} /><b className="small">{t.consultas}</b></div>
                  ))}</div>
                )}
              </div>
              <div className="card">
                <h3>Finalización por módulo</h3>
                <div className="mt">{p.finalizacion_modulos.map((m) => (
                  <div key={m.modulo} className="hbar"><span title={m.modulo} style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.modulo}</span><Barra valor={m.porcentaje} tono="mintbar" /><b className="small">{m.porcentaje}%</b></div>
                ))}</div>
              </div>
            </div>
          </>
        );
      }}
    </Vista>
  );
}
