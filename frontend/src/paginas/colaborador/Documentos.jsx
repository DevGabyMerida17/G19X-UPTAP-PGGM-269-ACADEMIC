import { useEffect, useState } from "react";
import { CircleAlert, Clock, FileCheck2, FileX2, Upload, X } from "lucide-react";
import { useResumen } from "../../App.jsx";
import { api } from "../../api.js";
import { Chip, Vista, fecha, useAccion } from "../../ui.jsx";

const ICONOS = {
  validado: [FileCheck2, "var(--mint)", "var(--mint-ink)"],
  revision: [Clock, "var(--butter)", "var(--butter-ink)"],
  rechazado: [FileX2, "var(--rose)", "var(--rose-ink)"],
  pendiente: [Upload, "var(--neutro)", "var(--muted)"],
};
const MAX_MB = 5;
const EXTENSIONES = ["pdf", "jpg", "jpeg", "png"];
const RECORDATORIO = `Solo se aceptan documentos en PDF, JPG o PNG de máximo ${MAX_MB} MB.`;

/** Devuelve el motivo por el que no se acepta el archivo, o "" si está bien. */
function problemaConArchivo(archivo) {
  const ext = archivo.name.includes(".") ? archivo.name.split(".").pop().toLowerCase() : "";
  if (!EXTENSIONES.includes(ext)) {
    return `"${archivo.name}" no es un tipo de archivo permitido. ${RECORDATORIO}`;
  }
  if (archivo.size > MAX_MB * 1024 * 1024) {
    return `"${archivo.name}" pesa ${(archivo.size / 1024 / 1024).toFixed(1)} MB. ${RECORDATORIO}`;
  }
  return "";
}

export default function Documentos() {
  const resumen = useResumen();
  const [ejecutar, ocupado] = useAccion();
  const [aviso, setAviso] = useState(null); // { tipoId, texto }
  const [sobre, setSobre] = useState(null); // documento sobre el que se está arrastrando

  // Evita que el navegador abra el archivo si se suelta fuera de un documento.
  useEffect(() => {
    const evitar = (e) => { if (e.dataTransfer?.types?.includes("Files")) e.preventDefault(); };
    window.addEventListener("dragover", evitar);
    window.addEventListener("drop", evitar);
    return () => { window.removeEventListener("dragover", evitar); window.removeEventListener("drop", evitar); };
  }, []);

  const subir = async (doc, archivos) => {
    setAviso(null);
    if (!archivos?.length) return;
    if (archivos.length > 1) { setAviso({ tipoId: doc.tipo_id, texto: "Sube un solo archivo por documento." }); return; }
    const archivo = archivos[0];
    const problema = problemaConArchivo(archivo);
    if (problema) { setAviso({ tipoId: doc.tipo_id, texto: problema }); return; }
    const ok = await ejecutar(() => api(`/api/yo/documentos/${doc.tipo_id}`, { metodo: "POST", archivo }), "Documento enviado a revisión");
    if (ok) resumen.recargar();
  };

  const soltar = (doc, puedeSubir) => (e) => {
    e.preventDefault();
    setSobre(null);
    if (!puedeSubir) {
      setAviso({ tipoId: doc.tipo_id, texto: "Este documento ya fue validado por RH; no es necesario volver a subirlo." });
      return;
    }
    if (!ocupado) subir(doc, e.dataTransfer.files);
  };

  return (
    <Vista estado={resumen}>
      {(d) => (
        <>
          <div className="head">
            <h1>Documentos requeridos</h1>
            <p className="muted">Sube los documentos solicitados por RH: usa el botón o arrastra el archivo sobre cada documento. {RECORDATORIO}</p>
          </div>
          <div className="stack">
            {d.documentos.map((doc) => {
              const [Icono, bg, fg] = ICONOS[doc.estado];
              const puedeSubir = doc.estado === "pendiente" || doc.estado === "rechazado" || doc.estado === "revision";
              const detalle = doc.estado === "rechazado" ? doc.nota
                : doc.estado === "pendiente" ? doc.descripcion
                : `${doc.archivo} · ${doc.estado === "validado" ? "validado" : "subido"} el ${fecha(doc.fecha, { day: "numeric", month: "long" })}`;
              const miAviso = aviso?.tipoId === doc.tipo_id ? aviso.texto : "";
              return (
                <div key={doc.tipo_id}>
                  <div
                    className={`doc ${doc.estado === "rechazado" ? "err" : ""} ${sobre === doc.tipo_id ? "arrastrando" : ""}`}
                    onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = puedeSubir ? "copy" : "none"; setSobre(doc.tipo_id); }}
                    onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setSobre(null); }}
                    onDrop={soltar(doc, puedeSubir)}
                  >
                    <div className="ic" style={{ background: bg, color: fg }} aria-hidden="true"><Icono size={20} strokeWidth={1.8} /></div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <b>{doc.titulo}</b>
                      <div className="small" style={{ color: doc.estado === "rechazado" ? "var(--rose-ink)" : "var(--muted)", overflowWrap: "anywhere" }}>
                        {sobre === doc.tipo_id && puedeSubir ? "Suelta aquí el archivo (PDF, JPG o PNG)" : detalle}
                      </div>
                    </div>
                    {doc.estado !== "pendiente" && doc.estado !== "rechazado" && <Chip estado={doc.estado} />}
                    {puedeSubir && (
                      <label className={`btn sm ${doc.estado === "rechazado" ? "rose" : "ghost"}`} aria-disabled={ocupado}>
                        {doc.estado === "pendiente" ? "Subir archivo" : doc.estado === "rechazado" ? "Volver a subir" : "Reemplazar"}
                        <input type="file" accept=".pdf,.jpg,.jpeg,.png" hidden disabled={ocupado}
                          onChange={(e) => { subir(doc, e.target.files); e.target.value = ""; }} />
                      </label>
                    )}
                  </div>
                  {miAviso && (
                    <div className="aviso-archivo" role="alert">
                      <CircleAlert size={18} strokeWidth={1.8} aria-hidden="true" />
                      <span>{miAviso}</span>
                      <button type="button" onClick={() => setAviso(null)} aria-label="Cerrar aviso"><X size={16} /></button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          <div className="notice mt">Recursos Humanos revisa cada documento. Si alguno se rechaza, aquí verás el motivo.</div>
        </>
      )}
    </Vista>
  );
}
