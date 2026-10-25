"""Reglas de validación compartidas para correos y nombres de personas."""
import re
import unicodedata

_CORREO = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")

# Palabras que pueden ir en minúscula dentro de un nombre: "María de la Luz", "Juan del Río"
PARTICULAS = {"de", "del", "la", "las", "los", "y", "e", "van", "von", "da", "di", "do", "dos", "das"}
_LETRAS = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"
_PALABRA = re.compile(rf"[{_LETRAS}]+")
_VOCALES = set("aeiouáéíóúü")


def validar_correo(v: str) -> str:
    """Sin espacios en ninguna parte (inicio, final ni en medio) y con formato válido."""
    if any(c.isspace() for c in v):
        raise ValueError("El correo no puede tener espacios.")
    if not _CORREO.fullmatch(v):
        raise ValueError("Escribe un correo válido, por ejemplo nombre@empresa.com.")
    return v.lower()


def validar_nombre(v: str) -> str:
    """Nombre de persona: solo letras, al menos nombre y apellido, y con forma de nombre real.

    Devuelve el nombre con espacios normalizados y en formato "Nombre Apellido".
    """
    v = unicodedata.normalize("NFC", v)
    if v != v.strip():
        raise ValueError("El nombre no puede empezar ni terminar con espacios.")
    if "  " in v:
        raise ValueError("Usa un solo espacio entre cada palabra del nombre.")
    if any(c.isdigit() for c in v):
        raise ValueError("El nombre no puede tener números.")
    palabras = v.split(" ")
    if any(not _PALABRA.fullmatch(p) for p in palabras):
        raise ValueError("El nombre solo puede tener letras (se permiten acentos y ñ).")
    principales = [p for p in palabras if p.lower() not in PARTICULAS]
    if len(principales) < 2:
        raise ValueError("Escribe el nombre completo: al menos un nombre y un apellido.")
    if len(palabras) > 7 or len(v) > 120:
        raise ValueError("El nombre es demasiado largo.")
    for p in principales:
        bajo = p.lower()
        if len(bajo) < 2:
            raise ValueError("Cada nombre y apellido debe tener al menos 2 letras.")
        if not set(bajo) & _VOCALES:
            raise ValueError(f"\"{p}\" no parece un nombre real.")
        if re.search(r"(.)\1\1", bajo) or len(set(bajo)) == 1:
            raise ValueError(f"\"{p}\" no parece un nombre real (tiene letras repetidas).")

    def formato(i: int, p: str) -> str:
        if i and p.lower() in PARTICULAS:
            return p.lower()
        resto = p[1:].lower() if p.isupper() or p.islower() else p[1:]  # respeta "McDonald"
        return p[:1].upper() + resto

    return " ".join(formato(i, p) for i, p in enumerate(palabras))


def nombre_de_pila(nombre: str | None) -> str | None:
    """Primer nombre para dirigirse a la persona, solo si el nombre guardado es un nombre real.

    Si alguien quedó registrado con números u otro identificador (por ejemplo "23344"), devuelve None
    para que los agentes y los correos no se dirijan a la persona por un número.
    """
    try:
        return validar_nombre((nombre or "").strip()).split(" ")[0]
    except ValueError:
        return None


def nombre_para_mostrar(nombre: str | None, correo: str = "") -> str:
    """Nombre completo si es un nombre real; si no, una etiqueta clara en lugar de un número."""
    if nombre_de_pila(nombre):
        return nombre.strip()
    return f"Sin nombre registrado ({correo})" if correo else "Sin nombre registrado"
