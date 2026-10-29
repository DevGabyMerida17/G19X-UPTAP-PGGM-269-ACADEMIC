import { useMemo, useState } from "react";
import { Check, Copy, Pencil, Trash2 } from "lucide-react";
import { useApp } from "../../App.jsx";
import { api } from "../../api.js";
import { errorCorreo, errorNombre, propsCorreo, propsNombre } from "../../validaciones.js";
import { Avatar, Barra, Chip, Vista, fecha, tonoBarra, useAccion, useApi, useEventos } from "../../ui.jsx";

const ROLES = { colaborador: "Colaborador", supervisor: "Supervisor / Responsable", rh: "Recursos Humanos" };
const sinAcentos = (t = "") => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export default function Colaboradores() {
  const { config, usuario } = useApp();
  const colaboradores = useApi("/api/rh/colaboradores");
  const personal = useApi("/api/rh/personal");
  const responsables = useApi("/api/rh/responsables");
  const programas = useApi("/api/rh/programas");
  const [vista, setVista] = useState("colaboradores");
  const [area, setArea] = useState("Todas");
  const [busca, setBusca] = useState("");
  const [formulario, setFormulario] = useState(false);
  const [confirmarBaja, setConfirmarBaja] = useState(null);
  const [confirmarTemporal, setConfirmarTemporal] = useState(null);
  const [confirmarEliminar, setConfirmarEliminar] = useState(null);
  const [credencial, setCredencial] = useState(null); // contraseña temporal recién generada, para que RH la copie
  const [ejecutar, ocupado] = useAccion();

  const recargar = () => { colaboradores.recargar(); personal.recargar(); responsables.recargar(); };
  useEventos(() => { colaboradores.recargar(); responsables.recargar(); });

  const cambiar = async (u, datos, aviso) => {
    const ok = await ejecutar(() => api(`/api/rh/usuarios/${u.id}`, { metodo: "PATCH", datos }), aviso);
    if (ok) recargar();
    return ok;
  };
  const nuevaTemporal = async (u) => {
    const r = await ejecutar(() => api(`/api/rh/usuarios/${u.id}/password-temporal`, { metodo: "POST" }));
    if (r) {
      setConfirmarTemporal(null);
      setCredencial({ nombre: u.nombre, correo: u.correo, password: r.password_temporal, correoConfigurado: r.correo_configurado });
      recargar();
      window.scrollTo(0, 0);
    }
  };
  const baja = async (u) => { if (await cambiar(u, { activo: false }, `${u.nombre} fue dado de baja`)) setConfirmarBaja(null); };
  const eliminar = async (u) => {
    if (await ejecutar(() => api(`/api/rh/usuarios/${u.id}`, { metodo: "DELETE" }), `${u.nombre} fue eliminado`)) {
      setConfirmarEliminar(null);
      recargar();
    }
  };
  const elegir = (accion, id) => { setConfirmarBaja(accion === "baja" ? id : null); setConfirmarTemporal(accion === "temporal" ? id : null);
    setConfirmarEliminar(accion === "eliminar" ? id : null); };

  const coincide = (u) => {
    const q = sinAcentos(busca.trim());
    return (area === "Todas" || u.area === area) &&
      (!q || [u.nombre, u.correo, u.puesto, u.supervisor].some((x) => sinAcentos(x || "").includes(q)));
  };

  const Estado = ({ u, children }) => (
    <>
      {children}
      {u.pendiente_activacion && u.activo && <div className="small muted mt-s nowrap">Aún con contraseña temporal</div>}
    </>
  );

  const AccionesUsuario = ({ u }) => {
    if (u.id === usuario.id) return null;
    if (confirmarEliminar === u.id) return (
      <div className="row nowrap" style={{ gap: 6, justifyContent: "flex-end" }}>
        <span className="small muted">¿Eliminar? Se borra todo su registro.</span>
        <button className="btn rose sm" disabled={ocupado} onClick={() => eliminar(u)}>Eliminar</button>
        <button className="btn ghost sm" onClick={() => elegir(null)}>Cancelar</button>
      </div>
    );
    return (
      <div className="row nowrap" style={{ gap: 6, justifyContent: "flex-end" }}>
        {u.activo && confirmarBaja !== u.id && (confirmarTemporal === u.id
          ? <><button className="btn sm" disabled={ocupado} onClick={() => nuevaTemporal(u)}>Generar</button>
              <button className="btn ghost sm" onClick={() => elegir(null)}>Cancelar</button></>
          : <button className="btn ghost sm" title="Genera una contraseña temporal nueva; la actual deja de funcionar"
              onClick={() => elegir("temporal", u.id)}>Contraseña temporal</button>)}
        {confirmarTemporal === u.id ? null : u.activo
          ? (confirmarBaja === u.id
            ? <><button className="btn rose sm" disabled={ocupado} onClick={() => baja(u)}>Confirmar baja</button>
                <button className="btn ghost sm" onClick={() => elegir(null)}>Cancelar</button></>
            : <button className="btn ghost sm" onClick={() => elegir("baja", u.id)}>Dar de baja</button>)
          : <button className="btn mint sm" disabled={ocupado} onClick={() => cambiar(u, { activo: true }, `${u.nombre} fue reactivado`)}>Reactivar</button>}
        {confirmarTemporal !== u.id && confirmarBaja !== u.id && (
          <button className="btn ghost sm" title={`Eliminar a ${u.nombre}`} aria-label={`Eliminar a ${u.nombre}`}
            onClick={() => elegir("eliminar", u.id)}><Trash2 size={15} /></button>)}
      </div>
    );
  };

  return (
    <>
      <div className="head row between wrap">
        <div><h1>Personal</h1><p className="muted">Da de alta al personal, asígnale un responsable y gestiona las bajas.</p></div>
        {!formulario && <button className="btn" onClick={() => setFormulario(true)}>+ Dar de alta</button>}
      </div>

      {credencial && <TarjetaCredencial {...credencial} alCerrar={() => setCredencial(null)} />}

      {formulario && (
        <NuevoUsuario config={config} programas={programas.datos || []} responsables={responsables.datos || []}
          alCerrar={() => setFormulario(false)}
          alGuardar={(c) => { setFormulario(false); setCredencial(c); recargar(); window.scrollTo(0, 0); }} />
      )}

      <div className="pestanas" role="tablist">
        <button role="tab" aria-selected={vista === "colaboradores"} className={vista === "colaboradores" ? "on" : ""} onClick={() => setVista("colaboradores")}>
          Colaboradores en capacitación {colaboradores.datos && <span className="cuenta">{colaboradores.datos.length}</span>}
        </button>
        <button role="tab" aria-selected={vista === "personal"} className={vista === "personal" ? "on" : ""} onClick={() => setVista("personal")}>
          Responsables y RH {personal.datos && <span className="cuenta">{personal.datos.length}</span>}
        </button>
      </div>

      <div className="filtros">
        <input type="search" placeholder="Buscar por nombre, correo, puesto o responsable" value={busca}
          onChange={(e) => setBusca(e.target.value)} aria-label="Buscar personal" />
        <div className="chips-area" role="group" aria-label="Filtrar por área">
          {["Todas", ...config.areas].map((a) => (
            <button key={a} className={area === a ? "on" : ""} aria-pressed={area === a} onClick={() => setArea(a)}>{a}</button>
          ))}
        </div>
      </div>

      {vista === "colaboradores" ? (
        <Vista estado={colaboradores}>
          {(lista) => {
            const filtrados = lista.filter(coincide);
            const areas = (area === "Todas" ? config.areas : [area]).map((a) => [a, filtrados.filter((c) => c.area === a)]);
            if (!filtrados.length) return <div className="notice">No hay colaboradores que coincidan con la búsqueda.</div>;
            return areas.filter(([, cs]) => cs.length).map(([a, cs]) => (
              <section key={a} className="card seccion-area">
                <div className="row between wrap">
                  <h3>{a}</h3>
                  <span className="small muted">{cs.length} {cs.length === 1 ? "persona" : "personas"} · {cs.filter((c) => !c.supervisor_id).length} sin responsable</span>
                </div>
                <div className="tablewrap mt-s"><table>
                  <thead><tr><th>Nombre</th><th>Responsable</th><th>Avance</th><th>Estado</th><th></th></tr></thead>
                  <tbody>{cs.map((c) => (
                    <tr key={c.id}>
                      <td><div className="row"><Avatar u={c} style={{ width: 30, height: 30, fontSize: 11 }} />
                        <div><NombreEditable u={c} alGuardar={recargar} /><div className="small muted">{c.puesto} · ingresó {fecha(c.fecha_ingreso)}</div>
                          <div className="small muted">{c.correo}</div></div></div></td>
                      <td>
                        <select value={c.supervisor_id || ""} aria-label={`Responsable de ${c.nombre}`} disabled={!c.activo || ocupado}
                          className={c.supervisor_id ? "" : "sin-asignar"} style={{ minWidth: 150, padding: "5px 8px" }}
                          onChange={(e) => cambiar(c, { supervisor_id: e.target.value ? Number(e.target.value) : null },
                            e.target.value ? "Responsable asignado" : "Responsable quitado")}>
                          <option value="">Sin asignar</option>
                          <OpcionesResponsables lista={responsables.datos || []} />
                        </select>
                      </td>
                      <td><div className="row avance-celda"><Barra valor={c.avance} tono={tonoBarra(c.estado)} /><span className="small">{c.avance}%</span></div></td>
                      <td><Estado u={c}><Chip estado={c.estado} /></Estado></td>
                      <td><AccionesUsuario u={c} /></td>
                    </tr>
                  ))}</tbody>
                </table></div>
              </section>
            ));
          }}
        </Vista>
      ) : (
        <Vista estado={personal}>
          {(lista) => {
            const filtrados = lista.filter(coincide);
            if (!filtrados.length) return <div className="notice">No hay personal que coincida con la búsqueda.</div>;
            return (
              <div className="card"><div className="tablewrap"><table>
                <thead><tr><th>Nombre</th><th>Rol</th><th>Área</th><th>A su cargo</th><th>Estado</th><th></th></tr></thead>
                <tbody>{filtrados.map((u) => (
                  <tr key={u.id}>
                    <td><NombreEditable u={u} alGuardar={recargar} />{u.id === usuario.id && <span className="small muted"> (tú)</span>}<div className="small muted">{u.correo}</div></td>
                    <td>{ROLES[u.rol]}</td>
                    <td className="muted">{u.area}</td>
                    <td>{u.rol === "supervisor" ? `${u.a_cargo} ${u.a_cargo === 1 ? "colaborador" : "colaboradores"}` : "—"}</td>
                    <td><Estado u={u}>{u.activo ? <Chip estado="validado">Activo</Chip> : <Chip estado="inactivo" />}</Estado></td>
                    <td><AccionesUsuario u={u} /></td>
                  </tr>
                ))}</tbody>
              </table></div></div>
            );
          }}
        </Vista>
      )}
      <p className="small muted mt">Al dar de baja a una persona, ya no podrá entrar: verá un aviso de que su cuenta está inactiva. Si era responsable, sus colaboradores quedan sin asignar. El bote de basura elimina a la persona y todo su registro (avance, documentos y comentarios); no se puede deshacer.</p>
    </>
  );
}

/** Nombre de la persona con un botón para corregirlo (mismas reglas que al dar de alta).
    Si quedó registrado con números, se marca en rojo para que RH lo corrija. */
function NombreEditable({ u, alGuardar }) {
  const [editando, setEditando] = useState(false);
  const [error, setError] = useState("");
  const [ejecutar, ocupado] = useAccion();
  const invalido = !!errorNombre(u.nombre);

  const guardar = async (e) => {
    e.preventDefault();
    const nombre = new FormData(e.target).get("nombre");
    const err = errorNombre(nombre);
    setError(err);
    if (err) return;
    if (await ejecutar(() => api(`/api/rh/usuarios/${u.id}`, { metodo: "PATCH", datos: { nombre } }), "Nombre actualizado")) {
      setEditando(false);
      alGuardar();
    }
  };

  if (editando) {
    return (
      <form onSubmit={guardar} className="nombre-editable">
        <input type="text" name="nombre" defaultValue={invalido ? "" : u.nombre} placeholder="Nombre y apellido"
          autoFocus aria-label="Nombre completo" {...propsNombre} />
        <button className="btn sm" disabled={ocupado}>Guardar</button>
        <button type="button" className="btn ghost sm" onClick={() => { setEditando(false); setError(""); }}>Cancelar</button>
        <span className="err-msg" style={{ flexBasis: "100%" }}>{error}</span>
      </form>
    );
  }
  return (
    <span className="row" style={{ gap: 6, display: "inline-flex" }}>
      {invalido
        ? <b style={{ color: "var(--rose-ink)" }} title={`Registrado como "${u.nombre}"`}>Sin nombre registrado</b>
        : <b title={u.correo}>{u.nombre}</b>}
      <button type="button" className="link small" onClick={() => setEditando(true)} aria-label={`Corregir el nombre de ${u.correo}`}>
        <Pencil size={13} strokeWidth={1.8} />{invalido ? " Corregir" : ""}
      </button>
    </span>
  );
}

/** Muestra la contraseña temporal una sola vez para que RH la copie y la entregue. */
function TarjetaCredencial({ nombre, correo, password, nueva, correoConfigurado, alCerrar }) {
  return (
    <div className="card corner tint-mint credencial" role="status" style={{ marginBottom: 16 }}>
      <h3>{nueva ? `${nombre} ya tiene acceso` : `Nueva contraseña temporal para ${nombre}`}</h3>
      <p className="small mt-s">
        {correoConfigurado && <>Le enviamos estos datos a <b>{correo}</b>. </>}
        <b>Esta contraseña solo se muestra ahora</b>; si se pierde, genera otra.
      </p>
      <div className="credencial-datos mt">
        <DatoCopiable etiqueta="Correo" valor={correo}><b>{correo}</b></DatoCopiable>
        <DatoCopiable etiqueta="Contraseña temporal" valor={password}><code>{password}</code></DatoCopiable>
      </div>
      <div className="row mt wrap">
        <button className="btn ghost" onClick={alCerrar}>Listo</button>
      </div>
    </div>
  );
}

/** Un dato con su propio botón para copiar solo ese valor. */
function DatoCopiable({ etiqueta, valor, children }) {
  const [copiado, setCopiado] = useState(false);
  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(valor);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch { setCopiado(false); }
  };
  return (
    <div className="dato-copiable">
      <div style={{ minWidth: 0 }}>
        <span className="small muted">{etiqueta}</span>
        {children}
      </div>
      <button type="button" className={`boton-copiar ${copiado ? "ok" : ""}`} onClick={copiar}
        aria-label={copiado ? `${etiqueta} copiado` : `Copiar ${etiqueta.toLowerCase()}`} title={copiado ? "Copiado" : `Copiar ${etiqueta.toLowerCase()}`}>
        {copiado ? <><Check size={16} strokeWidth={2.2} />Copiado</> : <><Copy size={16} strokeWidth={1.8} />Copiar</>}
      </button>
    </div>
  );
}

/** Responsables agrupados por área dentro del selector. */
function OpcionesResponsables({ lista, conCarga = false }) {
  const areas = [...new Set(lista.map((s) => s.area))];
  return areas.map((a) => (
    <optgroup key={a} label={a}>
      {lista.filter((s) => s.area === a).map((s) => (
        <option key={s.id} value={s.id}>{s.nombre}{conCarga ? ` (${s.a_cargo} a cargo)` : ""}</option>
      ))}
    </optgroup>
  ));
}

function NuevoUsuario({ config, programas, responsables, alCerrar, alGuardar }) {
  const [rol, setRol] = useState("colaborador");
  const [area, setArea] = useState(config.areas[0]);
  const [ejecutar, ocupado] = useAccion();
  const [errores, setErrores] = useState({});
  // Primero se sugieren los responsables del área elegida
  const ordenados = useMemo(() => [...responsables].sort((a, b) => (b.area === area) - (a.area === area)), [responsables, area]);

  const guardar = async (e) => {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.target));
    const err = { nombre: errorNombre(f.nombre), correo: errorCorreo(f.correo) };
    setErrores(err);
    if (err.nombre || err.correo) { e.target.elements[err.nombre ? "nombre" : "correo"].focus(); return; }
    const datos = { nombre: f.nombre, correo: f.correo, rol, puesto: f.puesto, area, fecha_ingreso: f.fecha_ingreso };
    if (rol === "colaborador") {
      datos.programa_id = Number(f.programa_id);
      datos.supervisor_id = f.supervisor_id ? Number(f.supervisor_id) : null;
    }
    const r = await ejecutar(() => api("/api/rh/usuarios", { metodo: "POST", datos }));
    if (r) alGuardar({ nombre: r.nombre, correo: r.correo, password: r.password_temporal, nueva: true, correoConfigurado: r.correo_configurado });
  };

  return (
    <form className="card corner tint-lav" onSubmit={guardar} style={{ marginBottom: 16 }}>
      <h3>Dar de alta</h3>
      <p className="small mt-s">Al guardar verás una contraseña temporal para entregarle a la persona. En su primer inicio de sesión tendrá que crear la suya.</p>
      <div className="grid g3 mt">
        <label className="field">Rol
          <select value={rol} onChange={(e) => setRol(e.target.value)}>
            {Object.entries(ROLES).map(([v, t]) => <option key={v} value={v}>{t}</option>)}
          </select>
        </label>
        <label className="field">Nombre completo
          <input type="text" name="nombre" required autoComplete="off" placeholder="Ej. María López Ruiz" {...propsNombre} />
          <span className="err-msg">{errores.nombre}</span></label>
        <label className="field">Correo corporativo
          <input type="text" inputMode="email" name="correo" required autoComplete="off" placeholder="nombre@empresa.com" {...propsCorreo} />
          <span className="err-msg">{errores.correo}</span></label>
        <label className="field">Puesto<input type="text" name="puesto" required minLength={2} /></label>
        <label className="field">Área<select value={area} onChange={(e) => setArea(e.target.value)}>{config.areas.map((a) => <option key={a}>{a}</option>)}</select></label>
        <label className="field">Fecha de ingreso<input type="date" name="fecha_ingreso" required defaultValue={new Date().toISOString().slice(0, 10)} /></label>
        {rol === "colaborador" && (
          <>
            <label className="field">Programa<select name="programa_id">{programas.map((p) => <option key={p.id} value={p.id}>{p.titulo}</option>)}</select></label>
            <label className="field">Responsable
              <select name="supervisor_id" defaultValue="">
                <option value="">Sin asignar por ahora</option>
                <OpcionesResponsables lista={ordenados} conCarga />
              </select>
            </label>
          </>
        )}
      </div>
      <div className="row mt"><button className="btn" disabled={ocupado}>{ocupado ? "Guardando…" : "Dar de alta"}</button>
        <button type="button" className="btn ghost" onClick={alCerrar}>Cancelar</button></div>
    </form>
  );
}
