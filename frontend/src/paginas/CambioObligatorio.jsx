import { useState } from "react";
import { api } from "../api.js";
import { Contrasena, MarcoAcceso } from "./Acceso.jsx";
import { nombreDePila } from "../validaciones.js";

/** Primer inicio de sesión: la persona entró con la contraseña temporal que le dio RH y debe crear la suya. */
export default function CambioObligatorio({ usuario, alTerminar, salir }) {
  const [errores, setErrores] = useState({});
  const [errorGeneral, setErrorGeneral] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const enviar = async (e) => {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.target));
    const err = {};
    if (/\s/.test(f.nueva)) {
      err.nueva = "La contraseña no puede tener espacios.";
    } else if (f.nueva.length < 8 || !/\d/.test(f.nueva) || !/[a-zA-ZáéíóúñÁÉÍÓÚÑ]/.test(f.nueva)) {
      err.nueva = "Usa al menos 8 caracteres, con letras y al menos un número.";
    }
    if (f.nueva !== f.confirmar) err.confirmar = "Las contraseñas no coinciden.";
    setErrores(err); setErrorGeneral("");
    if (Object.keys(err).length) return;
    setOcupado(true);
    try {
      alTerminar(await api("/api/auth/cambiar-password", { metodo: "POST", datos: { nueva: f.nueva } }));
    } catch (er) { setErrorGeneral(er.message); } finally { setOcupado(false); }
  };

  return (
    <MarcoAcceso>
      <h2>{nombreDePila(usuario.nombre) ? `Hola, ${nombreDePila(usuario.nombre)}` : "Hola"}</h2>
      <p className="muted mt-s">Entraste con una contraseña temporal. Antes de continuar, crea tu propia contraseña; solo tú la conocerás.</p>
      <form className="stack mt" onSubmit={enviar} noValidate>
        <input type="email" name="usuario" autoComplete="username" value={usuario.correo} readOnly hidden />
        <label className="field">Contraseña nueva<Contrasena name="nueva" autoComplete="new-password" />
          <span className="hint">Mínimo 8 caracteres, con letras y al menos un número.</span>
          <span className="err-msg">{errores.nueva}</span></label>
        <label className="field">Confirmar contraseña<Contrasena name="confirmar" autoComplete="new-password" />
          <span className="err-msg">{errores.confirmar}</span></label>
        <p className="err-msg" role="alert">{errorGeneral}</p>
        <button className="btn full" disabled={ocupado}>{ocupado ? "Guardando…" : "Guardar y entrar"}</button>
      </form>
      <p className="small mt" style={{ textAlign: "center" }}><button className="link" onClick={salir}>Salir</button></p>
    </MarcoAcceso>
  );
}
