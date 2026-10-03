# src/core/niah.py
import ollama
from src.config import NIAH_PROMPT
from src.core.router import elegir_modelo
from src.core.history import init_db, guardar_mensaje, obtener_historial
from src.rag.retriever import buscar_contexto


def _contexto_archivos_subidos(project_id: str, max_bytes_total: int = 30000) -> str:
    """
    Lee todos los archivos subidos a un proyecto y los formatea como contexto.
    Limita por archivo (8KB) y total (30KB por defecto).
    """
    try:
        import sqlite3
        from src.rag.indexer import DOCS_DIR, leer_documento

        docs_dir = DOCS_DIR / project_id
        if not docs_dir.exists():
            return ""

        bloques = []
        total = 0

        for f in sorted(docs_dir.iterdir()):
            if not f.is_file():
                continue
            # Ignorar backups
            if ".bak" in f.name:
                continue

            try:
                contenido = leer_documento(f)
            except Exception:
                continue

            if not contenido.strip():
                continue

            # Truncar por archivo
            if len(contenido) > 8000:
                contenido = contenido[:8000] + "\n... (truncado)"

            bloque = f"\n=== ARCHIVO SUBIDO: {f.name} ===\n{contenido}\n"

            if total + len(bloque) > max_bytes_total:
                bloques.append(
                    f"\n=== ARCHIVO SUBIDO: {f.name} === (no incluido, límite alcanzado)"
                )
                continue

            bloques.append(bloque)
            total += len(bloque)

        return "".join(bloques)
    except Exception:
        return ""


def _mensajes(mensaje: str, chat_id: str, project_id: str = None) -> list:
    """Construye los mensajes incluyendo historial y contexto RAG (si hay)."""
    historial = obtener_historial(chat_id, limit=20)
    mensajes = [{"role": "system", "content": NIAH_PROMPT}]

    # Instrucción para manejar contexto del sistema
    mensajes.append({
        "role": "system",
        "content": (
            "IMPORTANTE: En el historial puede haber bloques marcados como "
            "[CONTEXTO DEL SISTEMA]. Estos son resultados automáticos de acciones "
            "(compilar, test, ejecutar) que el usuario ejecutó. NO son preguntas "
            "del usuario y NO debes responderlos. Úsalos solo como contexto si el "
            "usuario pregunta algo relacionado. Si el usuario te saluda o pregunta "
            "algo no relacionado, ignora los bloques de contexto."
        ),
    })

    # Contexto RAG (búsqueda semántica en documentos indexados)
    if project_id:
        contexto = buscar_contexto(project_id, mensaje)
        if contexto:
            mensajes.append({
                "role": "system",
                "content": (
                    "A continuación tienes fragmentos relevantes de los documentos "
                    "del proyecto (búsqueda semántica). Úsalos si son útiles.\n\n"
                    f"{contexto}"
                ),
            })

        # Archivos subidos completos (lectura directa)
        archivos_subidos = _contexto_archivos_subidos(project_id)
        if archivos_subidos:
            mensajes.append({
                "role": "system",
                "content": (
                    "El usuario ha subido estos archivos al proyecto. "
                    "Léelos con atención para responder sus preguntas o trabajar con ellos:\n"
                    f"{archivos_subidos}"
                ),
            })

    # Añadir historial
    for h in historial:
        role = h["role"]
        content = h["content"]

        # Los mensajes de sistema van como "user" con prefijo especial
        # (Ollama solo permite un "system" al inicio)
        if role == "system":
            mensajes.append({
                "role": "user",
                "content": f"[CONTEXTO DEL SISTEMA - NO RESPONDER DIRECTAMENTE]\n{content}",
            })
            mensajes.append({
                "role": "assistant",
                "content": "Entendido, tomo nota de ese contexto.",
            })
        else:
            mensajes.append({"role": role, "content": content})

    mensajes.append({"role": "user", "content": mensaje})
    return mensajes


def chat(mensaje: str, chat_id: str, project_id: str = None) -> dict:
    init_db()
    modelo = elegir_modelo(mensaje)
    mensajes = _mensajes(mensaje, chat_id, project_id)

    guardar_mensaje(chat_id, "user", mensaje)
    respuesta = ollama.chat(model=modelo, messages=mensajes)
    contenido = respuesta["message"]["content"]
    guardar_mensaje(chat_id, "assistant", contenido, modelo)

    return {"respuesta": contenido, "modelo": modelo}


def stream(mensaje: str, chat_id: str, project_id: str = None):
    init_db()
    modelo = elegir_modelo(mensaje)
    mensajes = _mensajes(mensaje, chat_id, project_id)
    guardar_mensaje(chat_id, "user", mensaje)

    stream_resp = ollama.chat(model=modelo, messages=mensajes, stream=True)
    full = ""
    for chunk in stream_resp:
        token = chunk["message"]["content"]
        if token:
            full += token
            yield token

    guardar_mensaje(chat_id, "assistant", full, modelo)
