# src/rag/indexer.py
from pathlib import Path
from typing import List
import ollama
import chromadb
from chromadb.config import Settings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader


# Directorio donde se guardan los documentos subidos
DOCS_DIR = Path("rag_docs")
DOCS_DIR.mkdir(exist_ok=True)

# Directorio persistente de ChromaDB
CHROMA_DIR = Path("rag_chroma")
CHROMA_DIR.mkdir(exist_ok=True)

# Modelo de embeddings
EMBED_MODEL = "nomic-embed-text"

# Cliente ChromaDB persistente
_client = chromadb.PersistentClient(
    path=str(CHROMA_DIR),
    settings=Settings(anonymized_telemetry=False),
)


def _leer_pdf(path: Path) -> str:
    """Extrae texto de un PDF."""
    reader = PdfReader(str(path))
    texto = []
    for page in reader.pages:
        texto.append(page.extract_text() or "")
    return "\n".join(texto)


def _leer_texto(path: Path) -> str:
    """Lee un archivo de texto plano / markdown / código."""
    return path.read_text(encoding="utf-8", errors="ignore")


def leer_documento(path: Path) -> str:
    """Lee cualquier documento soportado."""
    if path.suffix.lower() == ".pdf":
        return _leer_pdf(path)
    return _leer_texto(path)


def _chunkear(texto: str) -> List[str]:
    """Divide el texto en fragmentos manejables."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(texto)


def _embed(textos: List[str]) -> List[List[float]]:
    """Convierte textos a vectores usando Ollama."""
    vectores = []
    for t in textos:
        resp = ollama.embeddings(model=EMBED_MODEL, prompt=t)
        vectores.append(resp["embedding"])
    return vectores


def indexar_documento(project_id: str, nombre_archivo: str, contenido: bytes) -> dict:
    """
    Guarda el archivo en disco, lo procesa y lo indexa en ChromaDB.
    Devuelve métricas del proceso.
    """
    # 1. Guardar archivo en disco
    proyecto_dir = DOCS_DIR / project_id
    proyecto_dir.mkdir(exist_ok=True)
    path = proyecto_dir / nombre_archivo
    path.write_bytes(contenido)

    # 2. Extraer texto
    texto = leer_documento(path)
    if not texto.strip():
        return {"error": "El documento no contiene texto extraíble"}

    # 3. Chunkear
    chunks = _chunkear(texto)

    # 4. Generar embeddings
    vectores = _embed(chunks)

    # 5. Guardar en ChromaDB (colección por proyecto)
    coleccion_nombre = f"proj_{project_id}"
    coleccion = _client.get_or_create_collection(name=coleccion_nombre)

    ids = [f"{nombre_archivo}_{i}" for i in range(len(chunks))]
    metadatas = [{"archivo": nombre_archivo, "chunk": i} for i in range(len(chunks))]

    coleccion.add(
        ids=ids,
        embeddings=vectores,
        documents=chunks,
        metadatas=metadatas,
    )

    return {
        "archivo": nombre_archivo,
        "chunks": len(chunks),
        "caracteres": len(texto),
    }


def listar_documentos(project_id: str) -> List[dict]:
    """Lista documentos indexados en un proyecto."""
    proyecto_dir = DOCS_DIR / project_id
    if not proyecto_dir.exists():
        return []
    return [
        {"nombre": f.name, "size": f.stat().st_size}
        for f in sorted(proyecto_dir.iterdir())
        if f.is_file()
    ]


def eliminar_documento(project_id: str, nombre_archivo: str) -> bool:
    """Elimina un documento y sus embeddings."""
    # Borrar archivo
    path = DOCS_DIR / project_id / nombre_archivo
    if path.exists():
        path.unlink()

    # Borrar embeddings
    coleccion_nombre = f"proj_{project_id}"
    try:
        coleccion = _client.get_collection(name=coleccion_nombre)
        # Obtener IDs que pertenecen a este archivo
        resultados = coleccion.get(where={"archivo": nombre_archivo})
        if resultados["ids"]:
            coleccion.delete(ids=resultados["ids"])
    except Exception:
        pass

    return True
