# src/api.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.agent import chat

app = FastAPI(title="Mi Agente IA Local", version="1.0.0")

# Permitir llamadas desde el frontend (React, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, reemplaza por tu dominio
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    mensaje: str


class ChatResponse(BaseModel):
    respuesta: str
    modelo: str


@app.get("/")
def root():
    return {"status": "ok", "mensaje": "API del agente IA funcionando"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/chat", response_model=ChatResponse)
def endpoint_chat(request: ChatRequest):
    """Recibe un mensaje y devuelve la respuesta del agente."""
    from src.config import MODEL_NAME
    respuesta = chat(request.mensaje)
    return ChatResponse(respuesta=respuesta, modelo=MODEL_NAME)
