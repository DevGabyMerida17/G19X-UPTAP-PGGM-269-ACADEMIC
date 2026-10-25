import { useEffect, useRef, useState } from "react";
import { Bot, Send } from "lucide-react";
import { useApp } from "../../App.jsx";
import { api } from "../../api.js";
import { TextoIA } from "../../ui.jsx";

const SUGERENCIAS = [
  "¿Quién va retrasado y por qué?",
  "¿Cuántos documentos faltan por revisar?",
  "Resume el avance del área de Desarrollo",
  "¿Quién no ha aprobado la evaluación de Seguridad?",
];

/** Asistente de RH: responde con los datos reales de la plataforma en este momento. */
export default function AsistenteRH() {
  const { config } = useApp();
  const nombre = config.agentes?.asistente_rh || "Asistente de RH";
  const [mensajes, setMensajes] = useState([
    { rol: "asistente", texto: `Hola, soy ${nombre}, tu Asistente de RH. Pregúntame sobre el avance del personal, documentos pendientes, evaluaciones o responsables; respondo con los datos actuales de la plataforma.` },
  ]);
  const [texto, setTexto] = useState("");
  const [pensando, setPensando] = useState(false);
  const caja = useRef(null);

  useEffect(() => { caja.current?.scrollTo(0, caja.current.scrollHeight); }, [mensajes, pensando]);

  const enviar = async (t) => {
    const pregunta = t.trim();
    if (!pregunta || pensando) return;
    const historial = mensajes.slice(1).filter((m) => m.rol !== "error").map((m) => ({ rol: m.rol === "usuario" ? "usuario" : "asistente", texto: m.texto }));
    setMensajes((prev) => [...prev, { rol: "usuario", texto: pregunta }]);
    setTexto("");
    setPensando(true);
    try {
      const r = await api("/api/rh/asistente", { metodo: "POST", datos: { pregunta, historial } });
      setMensajes((prev) => [...prev, { rol: "asistente", texto: r.respuesta }]);
    } catch (e) {
      setMensajes((prev) => [...prev, { rol: "error", texto: e.status === 503 ? "El asistente no puede responder porque la IA no está configurada en el servidor." : e.message }]);
    } finally {
      setPensando(false);
    }
  };

  return (
    <>
      <div className="head row" style={{ gap: 14 }}>
        <span className="agente-ico" style={{ width: 44, height: 44 }}><Bot size={22} strokeWidth={1.8} /></span>
        <div><h1>{nombre}</h1><p className="muted">Consulta el estado del onboarding con lenguaje natural. Solo usa los datos de la plataforma.</p></div>
      </div>
      <div className="chat">
        <div className="msgs" ref={caja} aria-live="polite">
          {mensajes.map((m, i) => (
            <div key={i} className={`msg ${m.rol === "usuario" ? "me" : m.rol === "error" ? "error" : "bot"}`}>{m.rol === "asistente" ? <TextoIA texto={m.texto} /> : m.texto}</div>
          ))}
          {pensando && <div className="msg bot muted">Revisando los datos…</div>}
        </div>
        <div className="sugs">
          {SUGERENCIAS.map((s) => <button key={s} onClick={() => enviar(s)} disabled={pensando}>{s}</button>)}
        </div>
        <form className="composer" onSubmit={(e) => { e.preventDefault(); enviar(texto); }}>
          <input type="text" value={texto} onChange={(e) => setTexto(e.target.value)} maxLength={1000}
            placeholder="Escribe tu pregunta…" aria-label="Tu pregunta" autoComplete="off" />
          <button className="btn" disabled={pensando || !texto.trim()}><Send size={16} strokeWidth={1.8} />Enviar</button>
        </form>
      </div>
    </>
  );
}
