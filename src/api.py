# src/api.py
import uuid
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, PlainTextResponse
from pydantic import BaseModel

from src.core import niah
from src.core.history import (
    init_db, crear_proyecto, listar_proyectos, eliminar_proyecto,
    crear_chat, listar_chats, eliminar_chat,
    obtener_historial, limpiar_historial,
)
from src.core.builder import crear_estructura_proyecto
from src.rag.indexer import (
    indexar_documento, listar_documentos, eliminar_documento,
)
from src.auth import (
    crear_token, verificar_credenciales, obtener_usuario_actual,
)

app = FastAPI(title="NIAH API", version="5.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


# ===== MODELOS =====

class LoginRequest(BaseModel):
    usuario: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChatRequest(BaseModel):
    mensaje: str
    chat_id: str
    project_id: str | None = None


class ChatResponse(BaseModel):
    respuesta: str
    modelo: str


class ProyectoRequest(BaseModel):
    nombre: str
    tipo: str = "python"


class ChatCreateRequest(BaseModel):
    titulo: str = "Nuevo chat"


# ===== PUBLICO =====

@app.get("/")
def root():
    return {"status": "ok", "agente": "NIAH"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/auth/login", response_model=TokenResponse)
def login(req: LoginRequest):
    """Valida usuario/contraseña y devuelve un JWT."""
    if not verificar_credenciales(req.usuario, req.password):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    token = crear_token(req.usuario)
    return TokenResponse(access_token=token)


@app.get("/auth/me")
def me(usuario: str = Depends(obtener_usuario_actual)):
    """Verifica que el token es válido."""
    return {"usuario": usuario}


# ===== PROTEGIDOS (requieren token) =====

@app.get("/projects")
def endpoint_listar_proyectos(usuario: str = Depends(obtener_usuario_actual)):
    return {"proyectos": listar_proyectos()}


@app.post("/projects")
def endpoint_crear_proyecto(
    req: ProyectoRequest, usuario: str = Depends(obtener_usuario_actual)
):
    project_id = str(uuid.uuid4())[:8]
    resultado = crear_estructura_proyecto(req.nombre, req.tipo)
    crear_proyecto(project_id, req.nombre, req.tipo)
    chat_id = str(uuid.uuid4())[:8]
    crear_chat(chat_id, project_id, "Chat inicial")
    return {
        "project_id": project_id,
        "chat_id": chat_id,
        "resultado": resultado,
    }


@app.delete("/projects/{project_id}")
def endpoint_eliminar_proyecto(
    project_id: str, usuario: str = Depends(obtener_usuario_actual)
):
    eliminar_proyecto(project_id)
    return {"status": "ok"}


@app.get("/projects/{project_id}/chats")
def endpoint_listar_chats(
    project_id: str, usuario: str = Depends(obtener_usuario_actual)
):
    return {"chats": listar_chats(project_id)}


@app.post("/projects/{project_id}/chats")
def endpoint_crear_chat(
    project_id: str,
    req: ChatCreateRequest,
    usuario: str = Depends(obtener_usuario_actual),
):
    chat_id = str(uuid.uuid4())[:8]
    crear_chat(chat_id, project_id, req.titulo)
    return {"chat_id": chat_id}


@app.delete("/chats/{chat_id}")
def endpoint_eliminar_chat(
    chat_id: str, usuario: str = Depends(obtener_usuario_actual)
):
    eliminar_chat(chat_id)
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def endpoint_chat(
    request: ChatRequest, usuario: str = Depends(obtener_usuario_actual)
):
    resultado = niah.chat(request.mensaje, request.chat_id, request.project_id)
    return ChatResponse(**resultado)


@app.post("/chat/stream")
def endpoint_chat_stream(
    request: ChatRequest, usuario: str = Depends(obtener_usuario_actual)
):
    return StreamingResponse(
        niah.stream(request.mensaje, request.chat_id, request.project_id),
        media_type="text/plain",
    )


@app.get("/chats/{chat_id}/history")
def endpoint_historial(
    chat_id: str, usuario: str = Depends(obtener_usuario_actual)
):
    return {"historial": obtener_historial(chat_id)}


@app.delete("/chats/{chat_id}/history")
def endpoint_limpiar(
    chat_id: str, usuario: str = Depends(obtener_usuario_actual)
):
    limpiar_historial(chat_id)
    return {"status": "ok"}


# ===== RAG =====

@app.get("/projects/{project_id}/documents")
def endpoint_listar_documentos(
    project_id: str, usuario: str = Depends(obtener_usuario_actual)
):
    return {"documentos": listar_documentos(project_id)}


@app.post("/projects/{project_id}/documents")
async def endpoint_subir_documento(
    project_id: str,
    file: UploadFile = File(...),
    usuario: str = Depends(obtener_usuario_actual),
):
    contenido = await file.read()
    try:
        resultado = indexar_documento(project_id, file.filename, contenido)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if "error" in resultado:
        raise HTTPException(status_code=400, detail=resultado["error"])
    return resultado


@app.delete("/projects/{project_id}/documents/{nombre}")
def endpoint_eliminar_documento(
    project_id: str,
    nombre: str,
    usuario: str = Depends(obtener_usuario_actual),
):
    eliminar_documento(project_id, nombre)
    return {"status": "ok"}


# ===== EXPORTAR CHAT =====

@app.get("/chats/{chat_id}/export")
def endpoint_exportar_chat(
    chat_id: str, usuario: str = Depends(obtener_usuario_actual)
):
    import sqlite3
    from datetime import datetime

    historial = obtener_historial(chat_id, limit=1000)
    if not historial:
        raise HTTPException(status_code=404, detail="Chat vacío o no encontrado")

    titulo = "Chat"
    project_id = None
    conn = sqlite3.connect("niah_history.db")
    c = conn.cursor()
    c.execute("SELECT titulo, project_id FROM chats WHERE id = ?", (chat_id,))
    row = c.fetchone()
    conn.close()
    if row:
        titulo = row[0]
        project_id = row[1]

    lineas = [
        f"# {titulo}",
        "",
        f"**Proyecto:** {project_id or 'N/A'}  ",
        f"**Chat ID:** {chat_id}  ",
        f"**Exportado:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "---",
        "",
    ]

    for msg in historial:
        autor = "**Tú**" if msg["role"] == "user" else "**NIAH**"
        modelo = f" _(modelo: {msg['model']})_" if msg.get("model") else ""
        lineas.append(f"### {autor}{modelo}")
        lineas.append("")
        lineas.append(msg["content"])
        lineas.append("")

    contenido = "\n".join(lineas)
    return PlainTextResponse(
        content=contenido,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="{titulo.replace(" ", "_")}.md"'
        },
    )
