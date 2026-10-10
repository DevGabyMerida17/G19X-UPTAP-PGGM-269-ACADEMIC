import { useEffect, useRef, useState } from "react";
import { Check, Download, Eye, FileText, X } from "lucide-react";
import { api, descargar, obtenerArchivo } from "../../api.js";
import { Chip, Vista, fecha, useAccion, useApi, useEventos } from "../../ui.jsx";

const rutaArchivo = (d) => `/api/rh/documentos/${d.id}/archivo`;

export default function Revision() {
  const docs = useApi("/api/rh/documentos");
  const [rechazando, setRechazando] = useState(null);
  const [vistaPrevia, setVistaPrevia] = useState(null); // documento abierto en la ventana
  const [ejecutar, ocupado] = useAccion();
  useEventos((e) => { if (e.tipo === "documento") docs.recargar(); });

  const validar = async (d) => {
    const ok = await ejecutar(() => api(`/api/rh/documentos/${d.id}/validar`, { metodo: "POST" }), "Documento validado");
    if (ok) { setVistaPrevia(null); docs.recargar(); }
  };
  const rechazar = async (id, nota) => {
    const ok = await ejecutar(() => api(`/api/rh/documentos/${id}/rechazar`, { metodo: "POST", datos: { nota } }), "Documento rechazado");
    if (ok) { setRechazando(null); setVistaPrevia(null); docs.recargar(); }
    return ok;
  };

  const FormRechazo = ({ d }) => (
    <form className="row" style={{ width: "100%" }} onSubmit={(e) => { e.preventDefault(); rechazar(d.id, new FormData(e.target).get("nota")); }}>
      <input type="text" name="nota" required minLength={3} placeholder="Motivo del rechazo (lo verá el colaborador)" aria-label="Motivo del rechazo" autoFocus />
      <button className="btn rose sm" disabled={ocupado}>Confirmar</button>
      <button type="button" className="btn ghost sm" onClick={() => setRechazando(null)}>Cancelar</button>
    </form>
  );

  return (
    <>
      <div className="head"><h1>Revisión de documentos</h1><p className="muted">Revisa, valida o rechaza los documentos que suben los colaboradores.</p></div>
      <Vista estado={docs}>
        {(lista) => {
          const pendientes = lista.filter((d) => d.estado === "revision");
          const resto = lista.filter((d) => d.estado !== "revision");
          return (
            <>
              <h2>Por revisar ({pendientes.length})</h2>
              {pendientes.length === 0 && <div className="notice mt">No hay documentos pendientes de revisión.</div>}
              <div className="stack mt">
                {pendientes.map((d) => (
                  <div key={d.id} className="doc" style={{ flexWrap: "wrap" }}>
                    <div className="ic" style={{ background: "var(--lav)", color: "var(--lav-ink)" }} aria-hidden="true"><FileText size={20} strokeWidth={1.8} /></div>
                    <div style={{ flex: 1, minWidth: 200 }}>
                      <b>{d.documento}</b>
                      <div className="small muted">{d.colaborador} · {d.puesto} · {fecha(d.fecha)}</div>
                      {d.archivo && <div className="small muted" style={{ overflowWrap: "anywhere" }}>{d.archivo}</div>}
                    </div>
                    <div className="row wrap" style={{ gap: 8 }}>
                      {d.tiene_archivo && (
                        <button className="btn ghost sm" onClick={() => setVistaPrevia(d)}><Eye size={15} strokeWidth={1.8} />Vista previa</button>
                      )}
                      <button className="btn mint sm" disabled={ocupado} onClick={() => validar(d)}><Check size={15} strokeWidth={2} />Validar</button>
                      <button className="btn rose sm" disabled={ocupado} onClick={() => setRechazando(d.id)}><X size={15} strokeWidth={2} />Rechazar</button>
                    </div>
                    {rechazando === d.id && <FormRechazo d={d} />}
                  </div>
                ))}
              </div>
              {resto.length > 0 && (
                <div className="card mt-l"><h3>Revisados recientemente</h3>
                  <div className="tablewrap mt-s"><table>
                    <thead><tr><th>Colaborador</th><th>Documento</th><th>Estado</th><th>Nota</th><th></th></tr></thead>
                    <tbody>{resto.slice(0, 20).map((d) => (
                      <tr key={d.id}>
                        <td>{d.colaborador}</td><td>{d.documento}</td><td><Chip estado={d.estado} /></td><td className="small muted">{d.nota}</td>
                        <td style={{ textAlign: "right" }}>{d.tiene_archivo && (
                          <button className="btn ghost sm" onClick={() => setVistaPrevia(d)} aria-label={`Vista previa de ${d.documento} de ${d.colaborador}`} title="Vista previa"><Eye size={15} strokeWidth={1.8} /></button>
                        )}</td>
                      </tr>
                    ))}</tbody>
                  </table></div>
                </div>
              )}
            </>
          );
        }}
      </Vista>

      {vistaPrevia && (
        <VentanaVistaPrevia doc={vistaPrevia} ocupado={ocupado} alCerrar={() => setVistaPrevia(null)}
          alDescargar={(blob) => ejecutar(() => descargar(rutaArchivo(vistaPrevia), vistaPrevia.archivo, blob), "Descarga iniciada")}
          alValidar={() => validar(vistaPrevia)} alRechazar={(nota) => rechazar(vistaPrevia.id, nota)} />
      )}
    </>
  );
}

/** Ventana encima de la página para ver el PDF o la imagen sin descargarlo. */
function VentanaVistaPrevia({ doc, ocupado, alCerrar, alDescargar, alValidar, alRechazar }) {
  const [archivo, setArchivo] = useState(null); // { url, blob, tipo }
  const [error, setError] = useState("");
  const [rechazando, setRechazando] = useState(false);
  const cerrarRef = useRef(null);

  useEffect(() => {
    let url;
    let cancelado = false;
    obtenerArchivo(rutaArchivo(doc))
      .then((blob) => {
        if (cancelado) return;
        url = URL.createObjectURL(blob);
        const ext = (doc.archivo.split(".").pop() || "").toLowerCase();
        const tipo = blob.type.includes("pdf") || ext === "pdf" ? "pdf"
          : blob.type.startsWith("image/") || ["jpg", "jpeg", "png"].includes(ext) ? "imagen" : "otro";
        setArchivo({ url, blob, tipo });
      })
      .catch((e) => !cancelado && setError(e.message));
    return () => { cancelado = true; if (url) URL.revokeObjectURL(url); };
  }, [doc]);

  // Cerrar con Esc, enfocar el botón de cerrar y evitar que la página de atrás se desplace.
  const alCerrarRef = useRef(alCerrar);
  alCerrarRef.current = alCerrar;
  useEffect(() => {
    cerrarRef.current?.focus();
    const tecla = (e) => { if (e.key === "Escape") alCerrarRef.current(); };
    document.addEventListener("keydown", tecla);
    const desborde = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", tecla); document.body.style.overflow = desborde; };
  }, []);

  const pendiente = doc.estado === "revision";

  return (
    <div className="modal-fondo" onMouseDown={(e) => { if (e.target === e.currentTarget) alCerrar(); }}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="titulo-vista">
        <div className="modal-cabecera">
          <div style={{ minWidth: 0 }}>
            <h3 id="titulo-vista">{doc.documento}</h3>
            <div className="small muted" style={{ overflowWrap: "anywhere" }}>{doc.colaborador} · {doc.archivo}</div>
          </div>
          <div className="row" style={{ gap: 8 }}>
            {!pendiente && <Chip estado={doc.estado} />}
            <button className="btn ghost sm" onClick={() => alDescargar(archivo?.blob)} disabled={!archivo}><Download size={15} strokeWidth={1.8} />Descargar</button>
            <button ref={cerrarRef} className="boton-tema" onClick={alCerrar} aria-label="Cerrar vista previa"><X size={18} /></button>
          </div>
        </div>

        <div className="modal-cuerpo">
          {error && <div className="notice rose">{error}</div>}
          {!archivo && !error && <p className="cargando" style={{ textAlign: "center" }}>Cargando documento…</p>}
          {archivo?.tipo === "pdf" && <iframe src={archivo.url} title={`Vista previa de ${doc.documento}`} />}
          {archivo?.tipo === "imagen" && <img src={archivo.url} alt={`${doc.documento} de ${doc.colaborador}`} />}
          {archivo?.tipo === "otro" && <div className="notice">Este tipo de archivo no se puede mostrar aquí. Usa “Descargar” para abrirlo.</div>}
        </div>

        {pendiente && (
          <div className="modal-pie">
            {rechazando ? (
              <form className="row" style={{ width: "100%" }} onSubmit={(e) => { e.preventDefault(); alRechazar(new FormData(e.target).get("nota")); }}>
                <input type="text" name="nota" required minLength={3} placeholder="Motivo del rechazo (lo verá el colaborador)" aria-label="Motivo del rechazo" autoFocus />
                <button className="btn rose sm" disabled={ocupado}>Confirmar rechazo</button>
                <button type="button" className="btn ghost sm" onClick={() => setRechazando(false)}>Cancelar</button>
              </form>
            ) : (
              <>
                <span className="small muted" style={{ marginRight: "auto" }}>¿El documento es correcto y legible?</span>
                <button className="btn rose sm" disabled={ocupado} onClick={() => setRechazando(true)}><X size={15} strokeWidth={2} />Rechazar</button>
                <button className="btn mint sm" disabled={ocupado} onClick={alValidar}><Check size={15} strokeWidth={2} />Validar</button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
