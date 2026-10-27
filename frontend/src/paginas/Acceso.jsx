import { useState } from "react";
import { ArrowRight, Lock, Mail, ShieldCheck } from "lucide-react";
import { api } from "../api.js";
import { BotonTema, Marca } from "../ui.jsx";
import { errorCorreo, propsCorreo, propsPassword } from "../validaciones.js";

/* Las cuentas las crea Recursos Humanos: aquí solo se inicia sesión o se recupera la contraseña. */

export function MarcoAcceso({ children }) {
  return (
    <div className="login">
      <BotonTema className="tema-acceso" />
      <section className="form">
        <div className="acceso-marca">
          <Marca grande />
          <div className="small muted">Plataforma de bienvenida para nuevos colaboradores</div>
        </div>
        <div className="acceso-tarjeta">{children}</div>
        <p className="small acceso-pie"><ShieldCheck size={16} strokeWidth={1.8} />Acceso exclusivo para el personal de PluriOne</p>
      </section>
    </div>
  );
}

export function Contrasena({ name, autoComplete, id }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="campo-pass campo-icono">
      <Lock size={18} strokeWidth={1.8} aria-hidden="true" />
      <input id={id} type={visible ? "text" : "password"} name={name} autoComplete={autoComplete} placeholder="••••••••••" {...propsPassword} />
      <button type="button" className="ver-pass" onClick={() => setVisible(!visible)}
        aria-label={visible ? "Ocultar contraseña" : "Mostrar contraseña"} aria-pressed={visible}>
        {visible ? "Ocultar" : "Mostrar"}
      </button>
    </div>
  );
}

const IconoMicrosoft = () => (
  <span className="sq" aria-hidden="true">
    <i style={{ background: "#F25022" }} /><i style={{ background: "#7FBA00" }} /><i style={{ background: "#00A4EF" }} /><i style={{ background: "#FFB900" }} />
  </span>
);

export function Aviso({ aviso }) {
  if (!aviso) return null;
  if (aviso.tipo === "baja") {
    return (
      <div className="notice rose aviso-acceso" role="alert">
        <b>Cuenta dada de baja</b>
        <p className="mt-s">{aviso.texto}</p>
      </div>
    );
  }
  return <div className={`notice ${aviso.tipo === "ok" ? "mint" : ""} aviso-acceso`} role="status">{aviso.texto}</div>;
}

export default function Acceso({ config, alEntrar, aviso }) {
  const [modo, setModo] = useState("login");
  return (
    <MarcoAcceso>
      {modo === "login"
        ? <Login config={config} alEntrar={alEntrar} avisoInicial={aviso} alOlvide={() => setModo("olvide")} />
        : <Olvide alVolver={() => setModo("login")} />}
    </MarcoAcceso>
  );
}

function Login({ config, alEntrar, avisoInicial, alOlvide }) {
  const [aviso, setAviso] = useState(avisoInicial);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const fallo = (err) => {
    if (err.codigo === "cuenta_inactiva") { setAviso({ tipo: "baja", texto: err.message }); setError(""); }
    else setError(err.message);
  };

  const enviar = async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    const errCorreo = errorCorreo(f.get("correo"));
    if (errCorreo) { setError(errCorreo); return; }
    if (!f.get("password")) { setError("Escribe tu contraseña."); return; }
    setOcupado(true); setError(""); setAviso(null);
    try {
      alEntrar(await api("/api/auth/login", { metodo: "POST", datos: { correo: f.get("correo"), password: f.get("password") } }));
    } catch (err) { fallo(err); } finally { setOcupado(false); }
  };

  const microsoft = async () => {
    setError(""); setAviso(null);
    if (!config.entra) {
      setAviso({ tipo: "info", texto: "El inicio de sesión con Microsoft todavía no está habilitado. Usa tu correo y contraseña." });
      return;
    }
    try {
      // Se carga solo cuando se usa, para que la página inicie más rápido.
      const { PublicClientApplication } = await import("@azure/msal-browser");
      const msal = new PublicClientApplication({
        auth: {
          clientId: config.entra.client_id,
          authority: `https://login.microsoftonline.com/${config.entra.tenant_id}`,
          redirectUri: window.location.origin,
        },
      });
      await msal.initialize();
      const r = await msal.loginPopup({ scopes: ["openid", "profile", "email"] });
      alEntrar(await api("/api/auth/microsoft", { metodo: "POST", datos: { id_token: r.idToken } }));
    } catch (err) {
      if (err?.errorCode !== "user_cancelled") fallo(err.status ? err : { message: err.message || "No se pudo iniciar sesión con Microsoft." });
    }
  };

  return (
    <>
      <h2>Bienvenido de nuevo</h2>
      <p className="muted mt-s">Inicia sesión para continuar con tu proceso de incorporación a PluriOne.</p>
      <div className="mt"><Aviso aviso={aviso} /></div>
      <form className="stack mt" onSubmit={enviar} noValidate>
        <label className="field">Correo
          <span className="campo-icono"><Mail size={18} strokeWidth={1.8} aria-hidden="true" />
            <input type="text" inputMode="email" name="correo" autoComplete="email" placeholder="nombre@empresa.com" {...propsCorreo} /></span>
        </label>
        <div className="field">
          <div className="row between"><label htmlFor="pass-login">Contraseña</label>
            <button type="button" className="link small" onClick={alOlvide}>¿Olvidaste tu contraseña?</button></div>
          <Contrasena id="pass-login" name="password" autoComplete="current-password" />
        </div>
        <p className="err-msg" role="alert">{error}</p>
        <button className="btn full" disabled={ocupado}>{ocupado ? "Entrando…" : <>Entrar <ArrowRight size={18} strokeWidth={2} /></>}</button>
      </form>

      <div className="divider"><span>o</span></div>
      <button className="btn ghost full ms" onClick={microsoft}>
        <IconoMicrosoft />Continuar con Microsoft
      </button>

      <p className="small muted mt" style={{ textAlign: "center" }}>
        ¿Eres nuevo? <b style={{ color: "var(--lav-ink)" }}>Recursos Humanos</b> crea tu cuenta y te entrega una contraseña temporal.
      </p>
    </>
  );
}

function Olvide({ alVolver }) {
  const [enviado, setEnviado] = useState("");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const enviar = async (e) => {
    e.preventDefault();
    const correo = new FormData(e.target).get("correo");
    const errCorreo = errorCorreo(correo);
    if (errCorreo) { setError(errCorreo); return; }
    setOcupado(true); setError("");
    try {
      const r = await api("/api/auth/olvide", { metodo: "POST", datos: { correo } });
      setEnviado(r.mensaje);
    } catch (err) { setError(err.message); } finally { setOcupado(false); }
  };

  return (
    <>
      <h2>¿Olvidaste tu contraseña?</h2>
      {enviado ? (
        <>
          <div className="notice mint mt" role="status">{enviado}</div>
          <button className="btn ghost full mt" onClick={alVolver}>Volver a iniciar sesión</button>
        </>
      ) : (
        <>
          <p className="muted mt-s">Escribe el correo de tu cuenta y te enviaremos un enlace para crear una contraseña nueva.</p>
          <form className="stack mt" onSubmit={enviar} noValidate>
            <label className="field">Correo
              <span className="campo-icono"><Mail size={18} strokeWidth={1.8} aria-hidden="true" />
                <input type="text" inputMode="email" name="correo" autoComplete="email" placeholder="nombre@empresa.com" autoFocus {...propsCorreo} /></span>
            </label>
            <p className="err-msg" role="alert">{error}</p>
            <button className="btn full" disabled={ocupado}>{ocupado ? "Enviando…" : "Enviar enlace"}</button>
          </form>
          <p className="small mt" style={{ textAlign: "center" }}><button className="link" onClick={alVolver}>← Volver a iniciar sesión</button></p>
        </>
      )}
    </>
  );
}
