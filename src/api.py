# src/api.py
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.core import niah
from src.core.history import (
    init_db, crear_proyecto, listar_proyectos, eliminar_proyecto,
    crear_chat, listar_chats, eliminar_chat,
    obtener_historial, limpiar_historial,
)
from src.core.builder import crear_estructura_proyecto

app = FastAPI(title="NIAH API", version="3.0.0")

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

class ChatRequest(BaseModel):
    mensaje: str
    chat_id: str


class ChatResponse(BaseModel):
    respuesta: str
    modelo: str


class ProyectoRequest(BaseModel):
    nombre: str
    tipo: str = "python"


class ChatCreateRequest(BaseModel):
    titulo: str = "Nuevo chat"


# ===== ROOT =====

@app.get("/")
def root():
    return {"status": "ok", "agente": "NIAH"}


@app.get("/health")
def health():
    return {"status": "healthy"}


# ===== PROYECTOS =====

@app.get("/projects")
def endpoint_listar_proyectos():
    return {"proyectos": listar_proyectos()}


@app.post("/projects")
def endpoint_crear_proyecto(req: ProyectoRequest):
    project_id = str(uuid.uuid4())[:8]
    # Crear estructura en disco
    resultado = crear_estructura_proyecto(req.nombre, req.tipo)
    # Registrar en DB
    crear_proyecto(project_id, req.nombre, req.tipo)
    # Crear primer chat por defecto
    chat_id = str(uuid.uuid4())[:8]
    crear_chat(chat_id, project_id, "Chat inicial")
    return {
        "project_id": project_id,
        "chat_id": chat_id,
        "resultado": resultado,
    }


@app.delete("/projects/{project_id}")
def endpoint_eliminar_proyecto(project_id: str):
    eliminar_proyecto(project_id)
    return {"status": "ok"}


# ===== CHATS =====

@app.get("/projects/{project_id}/chats")
def endpoint_listar_chats(project_id: str):
    return {"chats": listar_chats(project_id)}


@app.post("/projects/{project_id}/chats")
def endpoint_crear_chat(project_id: str, req: ChatCreateRequest):
    chat_id = str(uuid.uuid4())[:8]
    crear_chat(chat_id, project_id, req.titulo)
    return {"chat_id": chat_id}


@app.delete("/chats/{chat_id}")
def endpoint_eliminar_chat(chat_id: str):
    eliminar_chat(chat_id)
    return {"status": "ok"}


# ===== MENSAJES =====

@app.post("/chat", response_model=ChatResponse)
def endpoint_chat(request: ChatRequest):
    resultado = niah.chat(request.mensaje, request.chat_id)
    return ChatResponse(**resultado)


@app.post("/chat/stream")
def endpoint_chat_stream(request: ChatRequest):
    return StreamingResponse(
        niah.stream(request.mensaje, request.chat_id), media_type="text/plain"
    )


@app.get("/chats/{chat_id}/history")
def endpoint_historial(chat_id: str):
    return {"historial": obtener_historial(chat_id)}


@app.delete("/chats/{chat_id}/history")
def endpoint_limpiar(chat_id: str):
    limpiar_historial(chat_id)
    return {"status": "ok"}
