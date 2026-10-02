# src/rag/retriever.py
from typing import List
import ollama
import chromadb
from chromadb.config import Settings
from pathlib import Path

CHROMA_DIR = Path("rag_chroma")
EMBED_MODEL = "nomic-embed-text"

_client = chromadb.PersistentClient(
    path=str(CHROMA_DIR),
    settings=Settings(anonymized_telemetry=False),
)


def _embed(texto: str) -> List[float]:
    resp = ollama.embeddings(model=EMBED_MODEL, prompt=texto)
    return resp["embedding"]


def buscar_contexto(project_id: str, pregunta: str, top_k: int = 4) -> str:
    """
    Busca los fragmentos más relevantes en los documentos del proyecto.
    Devuelve un string con el contexto formateado (o vacío si no hay docs).
    """
    coleccion_nombre = f"proj_{project_id}"
    try:
        coleccion = _client.get_collection(name=coleccion_nombre)
    except Exception:
        return ""

    if coleccion.count() == 0:
        return ""

    vector = _embed(pregunta)
    resultados = coleccion.query(query_embeddings=[vector], n_results=top_k)

    if not resultados["documents"] or not resultados["documents"][0]:
        return ""

    fragmentos = []
    for i, doc in enumerate(resultados["documents"][0]):
        meta = resultados["metadatas"][0][i]
        fragmentos.append(
            f"[Fuente: {meta.get('archivo', 'desconocido')}]\n{doc}"
        )

    return "\n\n---\n\n".join(fragmentos)
