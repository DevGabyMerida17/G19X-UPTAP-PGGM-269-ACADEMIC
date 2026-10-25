import { useEffect, useRef, useState } from "react";
import { wsUrl } from "../../api.js";
import { TextoIA, Vista, useApi } from "../../ui.jsx";

const SUGERENCIAS = ["¿Qué me toca hacer ahora?", "¿Cómo puedo ver mis avances?", "¿Qué es una API?", "¿Cómo pido vacaciones?"];

export default function Tutor() {
  const historial = useApi("/api/tutor/historial");
  return (
    <>
      <div className="head">
        <h1>Tutor IA</h1>
        <p className="muted">Pregúntale lo que quieras: dudas sobre PluriOne, cualquier definición o tema que no entiendas, cómo usar la plataforma o qué te toca hacer.</p>
      </div>
      <Vista estado={historial}>{(h) => <Chat inicial={h.mensajes} iaConfigurada={h.ia_configurada} proveedor={h.proveedor} />}</Vista>
    </>
  );
}

function Chat({ inicial, iaConfigurada, proveedor }) {
  const [mensajes, setMensajes] = useState(inicial);
  const [escribiendo, setEscribiendo] = useState(false);
  const [conectado, setConectado] = useState(false);
  const [texto, setTexto] = useState("");
  const ws = useRef(null);
  const caja = useRef(null);

  useEffect(() => {
    let cerrado = false, reintento;
    const conectar = () => {
      const s = new WebSocket(wsUrl("/ws/tutor"));
      s.onopen = () => setConectado(true);
      s.onmessage = (e) => {
        const m = JSON.parse(e.data);
        if (m.tipo === "escribiendo") setEscribiendo(true);
        else {
          setEscribiendo(false);
          setMensajes((prev) => [...prev, m.tipo === "error"
            ? { rol: "error", texto: m.mensaje, fuentes: [] }
            : { rol: "tutor", texto: m.texto, fuentes: m.fuentes || [], agente: m.agente }]);
        }
      };
      s.onclose = (e) => {
        setConectado(false); setEscribiendo(false);
        if (!cerrado && e.code !== 4401) reintento = setTimeout(conectar, 3000);
      };
      ws.current = s;
    };
    conectar();
    return () => { cerrado = true; clearTimeout(reintento); ws.current?.close(); };
  }, []);

  useEffect(() => { caja.current?.scrollTo(0, caja.current.scrollHeight); }, [mensajes, escribiendo]);

  const enviar = (t) => {
    const pregunta = t.trim();
    if (!pregunta || escribiendo || ws.current?.readyState !== WebSocket.OPEN) return;
    setMensajes((prev) => [...prev, { rol: "usuario", texto: pregunta, fuentes: [] }]);
    ws.current.send(JSON.stringify({ pregunta }));
    setTexto("");
  };

  return (
    <>
      {iaConfigurada ? (
        <p className="small muted" style={{ marginBottom: 10 }}><span className="chip ok">IA conectada{proveedor ? ` · ${proveedor}` : ""}</span></p>
      ) : (
        <div className="notice peach" style={{ marginBottom: 16 }}>
          El Tutor todavía no puede responder porque el servidor no tiene conectado un modelo de inteligencia artificial.
          Recursos Humanos o el área de TI deben configurarlo.
        </div>
      )}
      <div className="chat">
        <div className="msgs" ref={caja} aria-live="polite">
          {mensajes.map((m, i) => (
            <div key={i} className={`msg ${m.rol === "usuario" ? "me" : m.rol === "error" ? "error" : "bot"}`}>
              {m.agente && <div className="msg-agente">{m.agente}</div>}
              {m.rol === "tutor" ? <TextoIA texto={m.texto} /> : m.texto}
              {m.fuentes?.length > 0 && <div className="src">Fuente: {m.fuentes.join(" · ")}</div>}
            </div>
          ))}
          {escribiendo && <div className="msg bot muted">Pensando…</div>}
        </div>
        <div className="sugs">
          {SUGERENCIAS.map((s) => <button key={s} onClick={() => enviar(s)} disabled={escribiendo || !conectado}>{s}</button>)}
        </div>
        <form className="composer" onSubmit={(e) => { e.preventDefault(); enviar(texto); }}>
          <input type="text" value={texto} onChange={(e) => setTexto(e.target.value)} maxLength={1000}
            placeholder={conectado ? "Escribe tu pregunta…" : "Conectando con el Tutor…"} aria-label="Tu pregunta" autoComplete="off" />
          <button className="btn" disabled={escribiendo || !conectado || !texto.trim()}>Enviar</button>
        </form>
      </div>
    </>
  );
}
