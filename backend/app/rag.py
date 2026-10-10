"""Base de conocimiento para el RAG (Retrieval-Augmented Generation).

Los documentos de la empresa viven en la tabla `documentos_conocimiento`
(RH los administra desde su panel). Cada documento se divide por secciones
("## Título") y se indexa con BM25 para encontrar los fragmentos más
relacionados con la pregunta del colaborador.
"""
import re
import threading
import unicodedata

from rank_bm25 import BM25Okapi
from langchain_core.documents import Document
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import DocumentoConocimiento

STOPWORDS = set(
    "a al ante con de del el en la las lo los para por que se su sus un una y o "
    "es son mi me te tu como cual cuando donde hay mas muy ya le les si no".split()
)

_lock = threading.Lock()
_indice: tuple[BM25Okapi, list[Document]] | None = None


def _singular(p: str) -> str:
    if len(p) > 5 and p.endswith("es"):
        return p[:-2]  # vacaciones -> vacacion
    if len(p) > 4 and p.endswith("s"):
        return p[:-1]  # sprints -> sprint
    return p


def normalizar(texto: str) -> list[str]:
    """Minúsculas, sin acentos, sin palabras vacías y en singular."""
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return [_singular(p) for p in re.findall(r"\w+", texto) if p not in STOPWORDS and len(p) > 1]


def fragmentar(titulo: str, tema: str, contenido: str) -> list[Document]:
    fragmentos = []
    for bloque in re.split(r"^## ", contenido, flags=re.M):
        bloque = bloque.strip()
        if not bloque:
            continue
        seccion, _, texto = bloque.partition("\n")
        seccion = seccion.strip().lstrip("# ").strip()
        fragmentos.append(Document(
            page_content=f"{titulo} - {seccion}\n{texto.strip()}",
            metadata={"fuente": f"{titulo} · {seccion}", "tema": tema or None},
        ))
    return fragmentos


def reconstruir(db: Session) -> None:
    """Se llama al iniciar y cada vez que RH cambia un documento."""
    global _indice
    docs = [f for d in db.scalars(select(DocumentoConocimiento))
            for f in fragmentar(d.titulo, d.tema, d.contenido)]
    with _lock:
        _indice = (BM25Okapi([normalizar(d.page_content) for d in docs]), docs) if docs else None


def buscar(pregunta: str, k: int = 4) -> list[Document]:
    """Los k fragmentos más relevantes (solo los que comparten alguna palabra con la pregunta)."""
    with _lock:
        indice = _indice
    if not indice:
        return []
    bm25, docs = indice
    puntajes = bm25.get_scores(normalizar(pregunta))
    orden = sorted(range(len(docs)), key=lambda i: puntajes[i], reverse=True)
    return [docs[i] for i in orden[:k] if puntajes[i] > 0]
