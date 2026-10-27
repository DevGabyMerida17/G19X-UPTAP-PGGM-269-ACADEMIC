from conftest import PASSWORD, ultimo_enlace


def test_no_hay_registro_publico(client):
    r = client.post("/api/auth/registro", json={"nombre": "X", "correo": "x@prueba.test", "password": "Clave12345"})
    assert r.status_code in (404, 405)


def test_alta_por_rh_con_password_temporal(client, admin):
    r = client.post("/api/rh/usuarios", headers=admin, json={
        "nombre": "Ana Torres", "correo": "Ana@Prueba.test", "puesto": "Desarrolladora", "area": "Desarrollo"})
    assert r.status_code == 200, r.text
    temporal = r.json()["password_temporal"]
    assert len(temporal) == 14 and r.json()["pendiente_activacion"] is True

    # Entra con la temporal, pero no puede usar la plataforma hasta crear su contraseña
    r = client.post("/api/auth/login", json={"correo": "ANA@prueba.test", "password": temporal})
    assert r.status_code == 200 and r.json()["usuario"]["debe_cambiar_password"] is True
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    r = client.get("/api/yo/resumen", headers=h)
    assert r.status_code == 403 and r.json()["detail"]["codigo"] == "cambio_obligatorio"

    assert client.post("/api/auth/cambiar-password", headers=h, json={"nueva": "corta"}).status_code == 422
    assert client.post("/api/auth/cambiar-password", headers=h, json={"nueva": temporal}).status_code == 400
    r = client.post("/api/auth/cambiar-password", headers=h, json={"nueva": "Segura2026"})
    assert r.status_code == 200 and r.json()["usuario"]["debe_cambiar_password"] is False
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/api/yo/resumen", headers=h).status_code == 200

    # La temporal ya no sirve
    assert client.post("/api/auth/login", json={"correo": "ana@prueba.test", "password": temporal}).status_code == 401
    assert client.post("/api/auth/login", json={"correo": "ana@prueba.test", "password": "Segura2026"}).status_code == 200
    client.post("/api/auth/salir", headers=h)
    assert client.get("/api/auth/yo", headers=h).status_code == 401


def test_rh_genera_nueva_password_temporal(client, admin, crear):
    h, uid = crear()
    correo = client.get("/api/auth/yo", headers=h).json()["correo"]
    temporal = client.post(f"/api/rh/usuarios/{uid}/password-temporal", headers=admin).json()["password_temporal"]
    assert client.get("/api/auth/yo", headers=h).status_code == 401  # se cierran sus sesiones
    assert client.post("/api/auth/login", json={"correo": correo, "password": PASSWORD}).status_code == 401
    r = client.post("/api/auth/login", json={"correo": correo, "password": temporal})
    assert r.json()["usuario"]["debe_cambiar_password"] is True


def test_olvide_password(client, crear):
    h, uid = crear()
    correo = client.get("/api/auth/yo", headers=h).json()["correo"]

    # La respuesta es la misma exista o no el correo
    r1 = client.post("/api/auth/olvide", json={"correo": "nadie@prueba.test"}).json()
    r2 = client.post("/api/auth/olvide", json={"correo": correo}).json()
    assert r1 == r2

    token = ultimo_enlace(correo, "restablecer")
    assert client.get(f"/api/auth/enlace/{token}").json()["tipo"] == "restablecer"
    assert client.post("/api/auth/nueva-password", json={"token": token, "password": "Nueva2026x"}).status_code == 200
    # Cambiar la contraseña cierra las sesiones abiertas
    assert client.get("/api/auth/yo", headers=h).status_code == 401
    assert client.post("/api/auth/login", json={"correo": correo, "password": PASSWORD}).status_code == 401
    assert client.post("/api/auth/login", json={"correo": correo, "password": "Nueva2026x"}).status_code == 200


def test_baja_de_usuario(client, admin, crear):
    h, uid = crear()
    correo = client.get("/api/auth/yo", headers=h).json()["correo"]
    r = client.patch(f"/api/rh/usuarios/{uid}", headers=admin, json={"activo": False})
    assert r.json()["estado"] == "inactivo"

    # Con la sesión abierta, su siguiente acción recibe el aviso de baja y la sesión se cierra
    r = client.get("/api/yo/resumen", headers=h)
    assert r.status_code == 403 and r.json()["detail"]["codigo"] == "cuenta_inactiva"
    assert client.get("/api/yo/resumen", headers=h).status_code == 401
    # Y al intentar entrar recibe el mensaje de baja
    r = client.post("/api/auth/login", json={"correo": correo, "password": PASSWORD})
    assert r.status_code == 403
    assert r.json()["detail"]["codigo"] == "cuenta_inactiva"
    assert "dada de baja" in r.json()["detail"]["mensaje"]
    # Aunque escriba mal la contraseña, se le dice que fue dado de baja (no "contraseña incorrecta")
    r = client.post("/api/auth/login", json={"correo": correo, "password": "OtraClave99"})
    assert r.status_code == 403 and r.json()["detail"]["codigo"] == "cuenta_inactiva"
    # Tampoco puede pedir cambio de contraseña
    client.post("/api/auth/olvide", json={"correo": correo})

    client.patch(f"/api/rh/usuarios/{uid}", headers=admin, json={"activo": True})
    assert client.post("/api/auth/login", json={"correo": correo, "password": PASSWORD}).status_code == 200


def test_rh_no_se_da_de_baja_a_si_mismo(client, admin):
    yo = client.get("/api/auth/yo", headers=admin).json()
    assert client.patch(f"/api/rh/usuarios/{yo['id']}", headers=admin, json={"activo": False}).status_code == 400


def test_permisos_por_rol(client, crear):
    h, _ = crear()
    assert client.get("/api/rh/panel", headers=h).status_code == 403
    assert client.get("/api/supervisor/equipo", headers=h).status_code == 403
    assert client.get("/api/yo/resumen").status_code == 401


def test_flujo_capacitacion(client, crear):
    h, _ = crear()
    res = client.get("/api/yo/resumen", headers=h).json()
    mods = res["modulos"]
    assert [m["estado"] for m in mods] == ["en_curso", "bloqueado", "bloqueado", "bloqueado"]
    assert res["avance"] == 0

    assert client.get(f"/api/yo/modulos/{mods[1]['id']}", headers=h).status_code == 403
    assert client.post(f"/api/yo/modulos/{mods[0]['id']}/completar", headers=h).status_code == 400

    for _ in range(mods[0]["total"]):
        client.post(f"/api/yo/modulos/{mods[0]['id']}/leer", headers=h)
    assert client.post(f"/api/yo/modulos/{mods[0]['id']}/completar", headers=h).status_code == 200

    mods = client.get("/api/yo/resumen", headers=h).json()["modulos"]
    assert mods[0]["estado"] == "completado" and mods[1]["estado"] == "en_curso"
    for _ in range(mods[1]["total"]):
        client.post(f"/api/yo/modulos/{mods[1]['id']}/leer", headers=h)
    client.post(f"/api/yo/modulos/{mods[1]['id']}/completar", headers=h)

    seg = client.get("/api/yo/resumen", headers=h).json()["modulos"][2]
    assert seg["tiene_evaluacion"]
    ev = client.get(f"/api/yo/modulos/{seg['id']}/evaluacion", headers=h).json()
    assert not ev["disponible"] and "correcta" not in ev["preguntas"][0]
    for _ in range(seg["total"]):
        client.post(f"/api/yo/modulos/{seg['id']}/leer", headers=h)

    mal = client.post(f"/api/yo/modulos/{seg['id']}/evaluacion", headers=h,
                      json={"respuestas": {str(p["id"]): 0 for p in ev["preguntas"]}}).json()
    assert not mal["aprobada"] and mal["calificacion"] == 25
    assert any(r["retroalimentacion"] for r in mal["resultado"])

    correctas = {"correo sospechoso": 1, "información de clientes": 2, "proteger tu cuenta": 0, "compartir tus": 1}
    elegir = lambda texto: next(v for k, v in correctas.items() if k in texto)  # noqa: E731
    bien = client.post(f"/api/yo/modulos/{seg['id']}/evaluacion", headers=h, json={"respuestas": {
        str(p["id"]): elegir(p["texto"]) for p in ev["preguntas"]}}).json()
    assert bien["aprobada"] and bien["calificacion"] == 100

    res = client.get("/api/yo/resumen", headers=h).json()
    assert res["modulos"][2]["estado"] == "completado"
    assert res["evaluaciones"][0]["calificacion"] == 100
    assert res["avance"] > 0


def test_documentos_y_revision_rh(client, admin, crear):
    h, _ = crear()
    tipo = client.get("/api/yo/resumen", headers=h).json()["documentos"][0]["tipo_id"]

    assert client.post(f"/api/yo/documentos/{tipo}", headers=h, files={"archivo": ("virus.exe", b"x")}).status_code == 400
    assert client.post(f"/api/yo/documentos/{tipo}", headers=h, files={"archivo": ("ine.pdf", b"%PDF-1.4 prueba")}).status_code == 200

    pendientes = [d for d in client.get("/api/rh/documentos", headers=admin).json() if d["estado"] == "revision"]
    did = pendientes[0]["id"]
    assert client.get(f"/api/rh/documentos/{did}/archivo", headers=admin).content.startswith(b"%PDF")
    client.post(f"/api/rh/documentos/{did}/rechazar", headers=admin, json={"nota": "Falta la firma"})
    doc = client.get("/api/yo/resumen", headers=h).json()["documentos"][0]
    assert doc["estado"] == "rechazado" and doc["nota"] == "Falta la firma"


def test_panel_y_responsables(client, admin):
    p = client.get("/api/rh/panel", headers=admin).json()
    luis = next(x for x in p["procesos"] if x["nombre"] == "Luis Ramírez")
    assert luis["estado"] == "completado" and luis["supervisor"] == "Jorge Castillo"
    assert next(x for x in p["procesos"] if x["nombre"] == "Sofía Méndez")["estado"] == "retrasado"

    resp = client.get("/api/rh/responsables", headers=admin).json()
    mariana = next(s for s in resp if s["nombre"] == "Mariana López")
    jorge = next(s for s in resp if s["nombre"] == "Jorge Castillo")

    # Reasignar a Luis con Mariana
    r = client.patch(f"/api/rh/usuarios/{luis['id']}", headers=admin, json={"supervisor_id": mariana["id"]})
    assert r.json()["supervisor"] == "Mariana López"
    # Quitar responsable
    r = client.patch(f"/api/rh/usuarios/{luis['id']}", headers=admin, json={"supervisor_id": None})
    assert r.json()["supervisor"] is None
    # Un colaborador no puede ser responsable
    assert client.patch(f"/api/rh/usuarios/{luis['id']}", headers=admin, json={"supervisor_id": luis["id"]}).status_code == 400
    client.patch(f"/api/rh/usuarios/{luis['id']}", headers=admin, json={"supervisor_id": jorge["id"]})

    personal = client.get("/api/rh/personal", headers=admin).json()
    assert {"rh", "supervisor"} <= {x["rol"] for x in personal}


def test_alta_de_supervisor_por_rh(client, admin):
    r = client.post("/api/rh/usuarios", headers=admin, json={
        "nombre": "Nuevo Supervisor", "correo": "nuevo.sup@prueba.test", "rol": "supervisor",
        "puesto": "Líder", "area": "Capacitación"})
    assert r.status_code == 200 and r.json()["rol"] == "supervisor" and r.json()["password_temporal"]
    r = client.post("/api/auth/login", json={"correo": "nuevo.sup@prueba.test", "password": r.json()["password_temporal"]})
    assert r.json()["usuario"]["rol"] == "supervisor"


def test_modulos_y_conocimiento_rh(client, admin):
    prog = client.get("/api/rh/programas", headers=admin).json()[1]["id"]
    m = client.post("/api/rh/modulos", headers=admin, json={
        "programa_id": prog, "titulo": "Cultura ágil", "minutos": 10,
        "contenido": "## Scrum\nTrabajamos en sprints de dos semanas.\n## Roles\nProduct Owner y Scrum Master."}).json()
    assert m["secciones"] == 2
    assert any(d["titulo"] == "Cultura ágil" for d in client.get("/api/rh/conocimiento", headers=admin).json())

    from app import rag
    assert any("sprints" in d.page_content for d in rag.buscar("¿cuánto dura un sprint?"))


def test_supervisor_ve_solo_a_sus_asignados(client, admin, crear):
    sup, sup_id = crear(rol="supervisor")
    h, uid = crear(supervisor_id=sup_id)
    _, otro = crear()  # mismo área, pero sin asignar a este supervisor

    eq = client.get("/api/supervisor/equipo", headers=sup).json()
    ids = [c["id"] for c in eq["colaboradores"]]
    assert uid in ids and otro not in ids
    assert client.get(f"/api/supervisor/colaboradores/{otro}", headers=sup).status_code == 404

    client.post(f"/api/supervisor/colaboradores/{uid}/comentarios", headers=sup, json={"texto": "Buen avance", "tipo": "comentario"})
    res = client.get("/api/yo/resumen", headers=h).json()
    assert res["observaciones"][0]["texto"] == "Buen avance"
    assert res["supervisor"]["nombre"] == "Persona Prueba"

    # Sin Azure OpenAI configurado la recomendación avisa claramente
    assert client.get(f"/api/supervisor/colaboradores/{uid}/recomendacion", headers=sup).status_code == 503


def test_tutor_sin_configurar(client, crear):
    h, _ = crear()
    token = h["Authorization"][7:]
    hist = client.get("/api/tutor/historial", headers=h).json()
    assert hist["ia_configurada"] is False and hist["mensajes"][0]["rol"] == "tutor"
    with client.websocket_connect(f"/ws/tutor?token={token}") as ws:
        ws.send_json({"pregunta": "¿Qué es Docker?"})
        r = ws.receive_json()
        assert r["tipo"] == "error" and "Azure OpenAI" in r["mensaje"]


def test_correo_sin_espacios(client, admin):
    for correo in [" ana@prueba.test", "ana@prueba.test ", "ana @prueba.test"]:
        r = client.post("/api/auth/login", json={"correo": correo, "password": "Clave12345"})
        assert r.status_code == 422 and "espacios" in r.text
        assert client.post("/api/auth/olvide", json={"correo": correo}).status_code == 422
        r = client.post("/api/rh/usuarios", headers=admin, json={
            "nombre": "Ana Torres", "correo": correo, "puesto": "Desarrolladora", "area": "Desarrollo"})
        assert r.status_code == 422 and "espacios" in r.text


def test_nombre_solo_letras_y_real(client, admin):
    def alta(nombre, correo):
        return client.post("/api/rh/usuarios", headers=admin, json={
            "nombre": nombre, "correo": correo, "puesto": "Analista", "area": "Desarrollo"})

    for malo in ["Ana", "Ana Torres2", "Ana 2", "Aaaa Pérez", "Xyz Pérez", " Ana Torres", "Ana  Torres", "Ana_Torres Ruiz"]:
        assert alta(malo, "malo@prueba.test").status_code == 422, malo

    r = alta("maría de la luz pérez", "maria.luz@prueba.test")
    assert r.status_code == 200 and r.json()["nombre"] == "María de la Luz Pérez"


def test_password_sin_espacios(client, crear):
    h, _ = crear()
    for mala in ["Clave 2026x", " Clave2026x", "Clave2026x "]:
        r = client.post("/api/auth/cambiar-password", headers=h, json={"nueva": mala})
        assert r.status_code == 422 and "espacios" in r.text


def test_alta_envia_datos_de_acceso_por_correo(client, admin):
    from conftest import CORREOS
    from email import policy
    from email.parser import BytesParser
    r = client.post("/api/rh/usuarios", headers=admin, json={
        "nombre": "Lucía Fernández", "correo": "lucia.fernandez@prueba.test", "puesto": "Analista", "area": "Desarrollo"})
    temporal = r.json()["password_temporal"]
    archivo = sorted(CORREOS.glob("*lucia.fernandez_at_prueba.test.eml"))[-1]
    msg = BytesParser(policy=policy.default).parsebytes(archivo.read_bytes())
    texto = msg.get_body(preferencelist=("plain",)).get_content()
    assert "datos de acceso" in msg["Subject"]
    assert "lucia.fernandez@prueba.test" in texto and temporal in texto


def _llegar_a_la_evaluacion(client, h):
    """Completa los dos primeros módulos y lee el de Seguridad; devuelve (modulo, evaluacion)."""
    mods = client.get("/api/yo/resumen", headers=h).json()["modulos"]
    for m in mods[:2]:
        for _ in range(m["total"]):
            client.post(f"/api/yo/modulos/{m['id']}/leer", headers=h)
        client.post(f"/api/yo/modulos/{m['id']}/completar", headers=h)
    seg = client.get("/api/yo/resumen", headers=h).json()["modulos"][2]
    for _ in range(seg["total"]):
        client.post(f"/api/yo/modulos/{seg['id']}/leer", headers=h)
    return seg, client.get(f"/api/yo/modulos/{seg['id']}/evaluacion", headers=h).json()


def test_limite_de_3_intentos_e_intento_extra(client, admin, crear):
    sup, sup_id = crear(rol="supervisor")
    h, uid = crear(supervisor_id=sup_id)
    seg, ev = _llegar_a_la_evaluacion(client, h)
    assert ev["intentos"] == {"usados": 0, "permitidos": 3, "restantes": 3, "aprobada": False, "agotados": False}

    mal = {"respuestas": {str(p["id"]): 0 for p in ev["preguntas"]}}
    for n in range(3):
        r = client.post(f"/api/yo/modulos/{seg['id']}/evaluacion", headers=h, json=mal).json()
        assert r["intentos"]["usados"] == n + 1 and r["evaluacion_id"]
    r = client.post(f"/api/yo/modulos/{seg['id']}/evaluacion", headers=h, json=mal)
    assert r.status_code == 403 and "3 intentos" in r.json()["detail"]

    # El responsable concede un intento más y se le avisa al colaborador
    r = client.post(f"/api/supervisor/colaboradores/{uid}/modulos/{seg['id']}/intento-extra", headers=sup)
    assert r.status_code == 200 and r.json()["restantes"] == 1
    assert "intento más" in client.get("/api/yo/resumen", headers=h).json()["observaciones"][0]["texto"]
    assert client.post(f"/api/yo/modulos/{seg['id']}/evaluacion", headers=h, json=mal).status_code == 200

    # RH también puede concederlo, y puede cambiar el máximo por módulo
    assert client.post(f"/api/supervisor/colaboradores/{uid}/modulos/{seg['id']}/intento-extra", headers=admin).status_code == 200
    r = client.patch(f"/api/rh/modulos/{seg['id']}", headers=admin, json={"intentos_maximos": 5})
    assert r.json()["intentos_maximos"] == 5
    client.patch(f"/api/rh/modulos/{seg['id']}", headers=admin, json={"intentos_maximos": 3})


def test_agentes_avisan_si_la_ia_no_esta_configurada(client, admin, crear):
    h, _ = crear()
    seg, ev = _llegar_a_la_evaluacion(client, h)
    r = client.post(f"/api/yo/modulos/{seg['id']}/evaluacion", headers=h,
                    json={"respuestas": {str(p["id"]): 0 for p in ev["preguntas"]}}).json()
    assert client.post(f"/api/yo/evaluaciones/{r['evaluacion_id']}/retroalimentacion", headers=h).status_code == 503
    assert client.get("/api/yo/recomendaciones", headers=h).status_code == 503
    assert client.post("/api/rh/asistente", headers=admin, json={"pregunta": "¿Quién va retrasado?"}).status_code == 503
    # Un colaborador no puede usar el Asistente de RH ni ver la evaluación de otro
    assert client.post("/api/rh/asistente", headers=h, json={"pregunta": "hola"}).status_code == 403
    otro, _ = crear()
    assert client.post(f"/api/yo/evaluaciones/{r['evaluacion_id']}/retroalimentacion", headers=otro).status_code == 404


def test_agentes_no_usan_numeros_como_nombre(client, admin, crear):
    from app.validaciones import nombre_de_pila, nombre_para_mostrar
    assert nombre_de_pila("23344") is None and nombre_de_pila("Ana Torres") == "Ana"
    assert nombre_para_mostrar("23344", "j@x.mx") == "Sin nombre registrado (j@x.mx)"

    h, uid = crear(nombre="23344")
    saludo = client.get("/api/tutor/historial", headers=h).json()["mensajes"][0]["texto"]
    assert saludo.startswith("¡Hola!") and "23344" not in saludo

    # RH corrige el nombre (con las mismas reglas) y el saludo ya usa el nombre real
    assert client.patch(f"/api/rh/usuarios/{uid}", headers=admin, json={"nombre": "Jesús 23"}).status_code == 422
    r = client.patch(f"/api/rh/usuarios/{uid}", headers=admin, json={"nombre": "jesús rizo"})
    assert r.json()["nombre"] == "Jesús Rizo"


def test_microsoft_completa_el_nombre_si_no_es_valido(client, crear, monkeypatch):
    from app.routers import auth
    h, uid = crear(nombre="23344")
    correo = client.get("/api/auth/yo", headers=h).json()["correo"]
    claims = {"oid": f"oid-{uid}", "preferred_username": correo, "name": "Jesús Rizo"}
    monkeypatch.setattr(auth, "validar_token_entra", lambda _t: claims)
    assert client.post("/api/auth/microsoft", json={"id_token": "x"}).json()["usuario"]["nombre"] == "Jesús Rizo"

    # Si ya tiene un nombre válido (el que puso RH), no se reemplaza.
    claims["name"] = "Otro Nombre"
    assert client.post("/api/auth/microsoft", json={"id_token": "x"}).json()["usuario"]["nombre"] == "Jesús Rizo"


def test_mi_equipo_marca_a_quien_agoto_sus_intentos(client, admin, crear):
    sup, sup_id = crear(rol="supervisor")
    h, uid = crear(supervisor_id=sup_id)
    crear(supervisor_id=sup_id)  # otro integrante que no ha reprobado
    seg, ev = _llegar_a_la_evaluacion(client, h)
    mal = {"respuestas": {str(p["id"]): 0 for p in ev["preguntas"]}}

    def fila():
        return next(c for c in client.get("/api/supervisor/equipo", headers=sup).json()["colaboradores"] if c["id"] == uid)

    for _ in range(2):
        client.post(f"/api/yo/modulos/{seg['id']}/evaluacion", headers=h, json=mal)
    assert fila()["escalados"] == []  # aún le queda un intento

    client.post(f"/api/yo/modulos/{seg['id']}/evaluacion", headers=h, json=mal)
    equipo = client.get("/api/supervisor/equipo", headers=sup).json()["colaboradores"]
    assert equipo[0]["id"] == uid  # aparece primero, sin abrir su detalle
    assert equipo[0]["escalados"] == [{"modulo_id": seg["id"], "modulo": seg["titulo"]}]
    assert all(c["escalados"] == [] for c in equipo[1:])

    # Con el intento extra deja de estar escalado.
    client.post(f"/api/supervisor/colaboradores/{uid}/modulos/{seg['id']}/intento-extra", headers=sup)
    assert fila()["escalados"] == []


def test_permisos_se_configuran_con_datos(client, admin, crear):
    """Dar o quitar un permiso a un rol es agregar o borrar una fila en rol_permisos, sin tocar el código."""
    from app.db import SessionLocal
    from app.models import RolPermiso
    sup, _ = crear(rol="supervisor")
    assert client.get("/api/rh/documentos", headers=sup).status_code == 403

    with SessionLocal() as db:
        db.add(RolPermiso(rol_clave="supervisor", permiso_clave="documentos.revisar"))
        db.commit()
    try:
        assert client.get("/api/rh/documentos", headers=sup).status_code == 200
        assert client.get("/api/rh/panel", headers=sup).status_code == 403  # solo ganó ese permiso
    finally:
        with SessionLocal() as db:
            db.delete(db.get(RolPermiso, ("supervisor", "documentos.revisar")))
            db.commit()
    assert client.get("/api/rh/documentos", headers=sup).status_code == 403

    roles = {r["clave"]: r["permisos"] for r in client.get("/api/rh/roles", headers=admin).json()}
    assert set(roles) == {"colaborador", "supervisor", "rh"}
    assert "documentos.revisar" in roles["rh"] and "documentos.revisar" not in roles["supervisor"]

    r = client.post("/api/rh/usuarios", headers=admin, json={
        "nombre": "Rol Inventado", "correo": "rol.inventado@prueba.test", "rol": "director", "puesto": "Director",
        "area": "Desarrollo"})
    assert r.status_code == 400  # solo se aceptan roles del catálogo
