"""Las pruebas usan SQLite y un Redis simulado para no depender de servicios externos."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

_tmp = tempfile.mkdtemp()
os.environ.update({
    "DATABASE_URL": f"sqlite:///{_tmp}/pruebas.db",
    "REDIS_URL": "memory://",
    "UPLOADS_DIR": f"{_tmp}/uploads",
    "CORREOS_DIR": f"{_tmp}/correos",
    "SMTP_HOST": "",
    "CARGAR_DATOS_DEMO": "true",
    "ADMIN_NOMBRE": "Admin Pruebas",
    "ADMIN_CORREO": "admin@prueba.test",
    "ADMIN_PASSWORD": "Admin12345",
    "AZURE_OPENAI_ENDPOINT": "",
    "AZURE_OPENAI_API_KEY": "",
    "AZURE_OPENAI_DEPLOYMENT": "",
})
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Programa, Usuario  # noqa: E402
from app.seguridad import hash_password  # noqa: E402

CORREOS = Path(_tmp) / "correos"
PASSWORD = "Clave12345"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin(client):
    r = client.post("/api/auth/login", json={"correo": "admin@prueba.test", "password": "Admin12345"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


_n = 0


@pytest.fixture
def crear(client):
    """Crea un usuario con contraseña directamente en la base y devuelve (headers, id)."""
    def _crear(rol="colaborador", area="Desarrollo", supervisor_id=None, nombre="Persona Prueba"):
        global _n
        _n += 1
        correo = f"persona{_n}@prueba.test"
        with SessionLocal() as db:
            prog = db.query(Programa).order_by(Programa.id).first()
            u = Usuario(nombre=nombre, correo=correo, password_hash=hash_password(PASSWORD), rol=rol, area=area,
                        puesto="Puesto", programa_id=prog.id if rol == "colaborador" else None,
                        supervisor_id=supervisor_id)
            db.add(u)
            db.commit()
            uid = u.id
        r = client.post("/api/auth/login", json={"correo": correo, "password": PASSWORD})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['token']}"}, uid
    return _crear


def ultimo_enlace(correo: str, tipo: str) -> str:
    """Lee el último correo guardado para esa persona y extrae el token del enlace."""
    import re
    from email import policy
    from email.parser import BytesParser
    archivos = sorted(CORREOS.glob(f"*{correo.replace('@', '_at_')}.eml"), key=lambda p: p.stat().st_mtime)
    assert archivos, f"No se envió correo a {correo}"
    msg = BytesParser(policy=policy.default).parsebytes(archivos[-1].read_bytes())
    texto = msg.get_body(preferencelist=("plain",)).get_content()
    return re.search(rf"\?{tipo}=([\w-]+)", texto).group(1)
