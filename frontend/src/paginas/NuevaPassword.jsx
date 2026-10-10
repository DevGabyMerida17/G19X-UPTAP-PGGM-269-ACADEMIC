import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Cargando } from "../ui.jsx";
import { Aviso, Contrasena, MarcoAcceso } from "./Acceso.jsx";

/** Se abre desde el enlace del correo: activar cuenta (invitación de RH) o restablecer contraseña. */
export default function NuevaPassword({ token, alTerminar }) {
  const [info, setInfo] = useState(null);
  const [errorEnlace, setErrorEnlace] = useState(null);
  const [errores, setErrores] = useState({});
  const [errorGeneral, setErrorGeneral] = useState("");
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    api(`/api/auth/enlace/${encodeURIComponent(token)}`)
      .then(setInfo)
      .catch((e) => setErrorEnlace(e.codigo === "cuenta_inactiva" ? { tipo: "baja", texto: e.message } : { tipo: "error", texto: e.message }));
  }, [token]);

  const enviar = async (e) => {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.target));
    const err = {};
    if (/\s/.test(f.password)) {
      err.password = "La contraseña no puede tener espacios.";
    } else if (f.password.length < 8 || !/\d/.test(f.password) || !/[a-zA-ZáéíóúñÁÉÍÓÚÑ]/.test(f.password)) {
      err.password = "Usa al menos 8 caracteres, con letras y al menos un número.";
    }
    if (f.password !== f.password2) err.password2 = "Las contraseñas no coinciden.";
    setErrores(err); setErrorGeneral("");
    if (Object.keys(err).length) return;
    setOcupado(true);
    try {
      await api("/api/auth/nueva-password", { metodo: "POST", datos: { token, password: f.password } });
      alTerminar(info.tipo === "activar"
        ? "¡Listo! Tu cuenta quedó activada. Ya puedes iniciar sesión."
        : "Tu contraseña se cambió. Ya puedes iniciar sesión con la nueva.");
    } catch (er) { setErrorGeneral(er.message); } finally { setOcupado(false); }
  };

  if (errorEnlace) {
    return (
      <MarcoAcceso>
        <h2>Enlace no disponible</h2>
        <div className="mt">{errorEnlace.tipo === "baja" ? <Aviso aviso={errorEnlace} /> : <div className="notice rose">{errorEnlace.texto}</div>}</div>
        <button className="btn ghost full mt" onClick={() => alTerminar(null)}>Ir a iniciar sesión</button>
      </MarcoAcceso>
    );
  }
  if (!info) return <MarcoAcceso><Cargando /></MarcoAcceso>;

  const activar = info.tipo === "activar";
  return (
    <MarcoAcceso>
      <h2>{activar ? `Hola, ${info.nombre.split(" ")[0]}` : "Crea una contraseña nueva"}</h2>
      <p className="muted mt-s">
        {activar ? "Recursos Humanos creó tu cuenta. Crea tu contraseña para entrar a la plataforma." : `Para la cuenta ${info.correo}.`}
      </p>
      <form className="stack mt" onSubmit={enviar} noValidate>
        <input type="email" name="usuario" autoComplete="username" value={info.correo} readOnly hidden />
        <label className="field">Contraseña nueva<Contrasena name="password" autoComplete="new-password" />
          <span className="hint">Mínimo 8 caracteres, con letras y al menos un número.</span>
          <span className="err-msg">{errores.password}</span></label>
        <label className="field">Confirmar contraseña<Contrasena name="password2" autoComplete="new-password" />
          <span className="err-msg">{errores.password2}</span></label>
        <p className="err-msg" role="alert">{errorGeneral}</p>
        <button className="btn full" disabled={ocupado}>{ocupado ? "Guardando…" : activar ? "Activar mi cuenta" : "Guardar contraseña"}</button>
      </form>
    </MarcoAcceso>
  );
}
