# src/api.py
import uuid
import sqlite3
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, PlainTextResponse
from pydantic import BaseModel

from src.core import niah
from src.core.history import (
    init_db, crear_proyecto, listar_proyectos, eliminar_proyecto,
    crear_chat, listar_chats, eliminar_chat,
    obtener_historial, limpiar_historial,
    verificar_propietario, verificar_chat_propietario,
)
from src.core.builder import crear_estructura_proyecto
from src.rag.indexer import (
    indexar_documento, listar_documentos, eliminar_documento,
)
from src.auth import (
    init_users_table, crear_usuario, verificar_credenciales,
    crear_token, obtener_usuario_actual, obtener_rol,
    listar_usuarios, eliminar_usuario,
)

app = FastAPI(title="NIAH API", version="6.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()
    init_users_table()


# ===== MODELOS =====

class LoginRequest(BaseModel):
    usuario: str
    password: str


class RegisterRequest(BaseModel):
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
    if not verificar_credenciales(req.usuario, req.password):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    return TokenResponse(access_token=crear_token(req.usuario))


@app.post("/auth/register", response_model=TokenResponse)
def register(req: RegisterRequest):
    if len(req.usuario) < 3:
        raise HTTPException(status_code=400, detail="Usuario muy corto (mín. 3)")
    if len(req.password) < 4:
        raise HTTPException(status_code=400, detail="Contraseña muy corta (mín. 4)")
    if not crear_usuario(req.usuario, req.password, "user"):
        raise HTTPException(status_code=400, detail="El usuario ya existe")
    return TokenResponse(access_token=crear_token(req.usuario))


@app.get("/auth/me")
def me(usuario: str = Depends(obtener_usuario_actual)):
    return {"usuario": usuario, "rol": obtener_rol(usuario)}


# ===== USUARIOS (solo admin) =====

@app.get("/users")
def endpoint_listar_usuarios(usuario: str = Depends(obtener_usuario_actual)):
    if obtener_rol(usuario) != "admin":
        raise HTTPException(status_code=403, detail="Solo admins")
    return {"usuarios": listar_usuarios()}


@app.delete("/users/{username}")
def endpoint_eliminar_usuario(
    username: str, usuario: str = Depends(obtener_usuario_actual)
):
    if obtener_rol(usuario) != "admin":
        raise HTTPException(status_code=403, detail="Solo admins")
    if not eliminar_usuario(username):
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar (no existe o es el admin principal)",
        )
    return {"status": "ok"}


# ===== PROYECTOS =====

@app.get("/projects")
def endpoint_listar_proyectos(usuario: str = Depends(obtener_usuario_actual)):
    return {"proyectos": listar_proyectos(usuario)}


@app.post("/projects")
def endpoint_crear_proyecto(
    req: ProyectoRequest, usuario: str = Depends(obtener_usuario_actual)
):
    project_id = str(uuid.uuid4())[:8]
    resultado = crear_estructura_proyecto(req.nombre, req.tipo)
    crear_proyecto(project_id, usuario, req.nombre, req.tipo)
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
    if not eliminar_proyecto(project_id, usuario):
        raise HTTPException(status_code=403, detail="No tienes permiso")
    return {"status": "ok"}


# ===== CHATS =====

@app.get("/projects/{project_id}/chats")
def endpoint_listar_chats(
    project_id: str, usuario: str = Depends(obtener_usuario_actual)
):
    if not verificar_propietario(project_id, usuario):
        raise HTTPException(status_code=403, detail="No tienes permiso")
    return {"chats": listar_chats(project_id)}


@app.post("/projects/{project_id}/chats")
def endpoint_crear_chat(
    project_id: str,
    req: ChatCreateRequest,
    usuario: str = Depends(obtener_usuario_actual),
):
    if not verificar_propietario(project_id, usuario):
        raise HTTPException(status_code=403, detail="No tienes permiso")
    chat_id = str(uuid.uuid4())[:8]
    crear_chat(chat_id, project_id, req.titulo)
    return {"chat_id": chat_id}


@app.delete("/chats/{chat_id}")
def endpoint_eliminar_chat(
    chat_id: str, usuario: str = Depends(obtener_usuario_actual)
):
    if not eliminar_chat(chat_id, usuario):
        raise HTTPException(status_code=403, detail="No tienes permiso")
    return {"status": "ok"}


# ===== MENSAJES =====

@app.post("/chat", response_model=ChatResponse)
def endpoint_chat(
    request: ChatRequest, usuario: str = Depends(obtener_usuario_actual)
):
    if not verificar_chat_propietario(request.chat_id, usuario):
        raise HTTPException(status_code=403, detail="No tienes permiso")
    resultado = niah.chat(request.mensaje, request.chat_id, request.project_id)
    return ChatResponse(**resultado)


@app.post("/chat/stream")
def endpoint_chat_stream(
    request: ChatRequest, usuario: str = Depends(obtener_usuario_actual)
):
    if not verificar_chat_propietario(request.chat_id, usuario):
        raise HTTPException(status_code=403, detail="No tienes permiso")
    return StreamingResponse(
        niah.stream(request.mensaje, request.chat_id, request.project_id),
        media_type="text/plain",
    )


@app.get("/chats/{chat_id}/history")
def endpoint_historial(
    chat_id: str, usuario: str = Depends(obtener_usuario_actual)
):
    if not verificar_chat_propietario(chat_id, usuario):
        raise HTTPException(status_code=403, detail="No tienes permiso")
    return {"historial": obtener_historial(chat_id)}


@app.delete("/chats/{chat_id}/history")
def endpoint_limpiar(
    chat_id: str, usuario: str = Depends(obtener_usuario_actual)
):
    if not limpiar_historial(chat_id, usuario):
        raise HTTPException(status_code=403, detail="No tienes permiso")
    return {"status": "ok"}


# ===== RAG =====

@app.get("/projects/{project_id}/documents")
def endpoint_listar_documentos(
    project_id: str, usuario: str = Depends(obtener_usuario_actual)
):
    if not verificar_propietario(project_id, usuario):
        raise HTTPException(status_code=403, detail="No tienes permiso")
    return {"documentos": listar_documentos(project_id)}


@app.post("/projects/{project_id}/documents")
async def endpoint_subir_documento(
    project_id: str,
    file: UploadFile = File(...),
    usuario: str = Depends(obtener_usuario_actual),
):
    if not verificar_propietario(project_id, usuario):
        raise HTTPException(status_code=403, detail="No tienes permiso")
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
    if not verificar_propietario(project_id, usuario):
        raise HTTPException(status_code=403, detail="No tienes permiso")
    eliminar_documento(project_id, nombre)
    return {"status": "ok"}


# ===== EXPORTAR =====

@app.get("/chats/{chat_id}/export")
def endpoint_exportar_chat(
    chat_id: str, usuario: str = Depends(obtener_usuario_actual)
):
    if not verificar_chat_propietario(chat_id, usuario):
        raise HTTPException(status_code=403, detail="No tienes permiso")

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


# ===== AGENT DEV: FASE A (Análisis + Stack + Estructura) =====

from src.agent_dev.analyzer import generar_plan_completo
from src.agent_dev.schemas import AnalyzeRequest, PlanCompleto


@app.post("/agent/analyze", response_model=PlanCompleto)
def endpoint_agent_analyze(
    req: AnalyzeRequest,
    usuario: str = Depends(obtener_usuario_actual),
):
    """
    Analiza el brief, elige el stack óptimo y propone la estructura.
    NO ejecuta nada, solo devuelve el plan para que el usuario lo apruebe.
    """
    try:
        plan = generar_plan_completo(req.brief, req.nombre_sugerido)
        return plan
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en análisis: {str(e)}")


# ===== AGENT DEV: FASE B (Generación de código) =====

import asyncio
import json as _json
from pathlib import Path as _Path
from fastapi.responses import StreamingResponse as _SR

from src.agent_dev.schemas import PlanCompleto, ExecuteRequest
from src.agent_dev.coder import generar_archivo
from src.agent_dev.file_writer import (
    crear_estructura, escribir_archivo, listar_proyectos_generados,
    eliminar_proyecto, GENERATED_DIR,
)
from src.agent_dev.job_manager import job_manager


async def _ejecutar_generacion(job, plan: PlanCompleto):
    """Corrutina que genera todos los archivos uno por uno."""
    try:
        job.estado = "generando"
        job.agregar_evento({
            "tipo": "inicio",
            "job_id": job.job_id,
            "nombre": job.nombre_proyecto,
            "total": job.total,
        })

        # Crear estructura de carpetas
        try:
            raiz = crear_estructura(
                plan.estructura.nombre_proyecto,
                plan.estructura.carpetas,
            )
            job.agregar_evento({
                "tipo": "estructura",
                "raiz": str(raiz),
                "carpetas": len(plan.estructura.carpetas),
            })
        except Exception as e:
            job.agregar_evento({"tipo": "error", "mensaje": f"Error creando estructura: {e}"})
            job.estado = "error"
            job.fin = __import__("datetime").datetime.now()
            return

        archivos_previos = {}
        exitos = 0
        errores = 0

        for i, archivo in enumerate(plan.estructura.archivos, start=1):
            if job.cancelado:
                job.agregar_evento({"tipo": "cancelado"})
                break

            job.actual = i
            # Elegir modelo y avisar
            from src.agent_dev.coder import elegir_modelo
            modelo = elegir_modelo(archivo.ruta)

            job.agregar_evento({
                "tipo": "archivo",
                "i": i,
                "total": job.total,
                "ruta": archivo.ruta,
                "estado": "generando",
                "modelo": modelo,
            })

            # Generar (bloqueante, pero dentro de un thread para no bloquear)
            resultado = await asyncio.to_thread(
                generar_archivo,
                plan,
                archivo.ruta,
                archivo.descripcion,
                archivos_previos,
            )

            if resultado["exito"]:
                # Escribir a disco
                try:
                    write_res = escribir_archivo(
                        raiz, archivo.ruta, resultado["contenido"]
                    )
                    archivos_previos[archivo.ruta] = resultado["contenido"]
                    exitos += 1
                    job.agregar_evento({
                        "tipo": "archivo",
                        "i": i,
                        "total": job.total,
                        "ruta": archivo.ruta,
                        "estado": "ok",
                        "bytes": write_res["bytes"],
                        "tiempo": resultado["tiempo"],
                        "modelo": resultado["modelo"],
                    })
                except Exception as e:
                    errores += 1
                    job.agregar_evento({
                        "tipo": "archivo",
                        "i": i,
                        "total": job.total,
                        "ruta": archivo.ruta,
                        "estado": "error_escritura",
                        "error": str(e),
                    })
            else:
                errores += 1
                job.agregar_evento({
                    "tipo": "archivo",
                    "i": i,
                    "total": job.total,
                    "ruta": archivo.ruta,
                    "estado": "error",
                    "error": resultado["error"],
                })

        # Fin
        job.estado = "terminado"
        from datetime import datetime as _dt
        job.fin = _dt.now()
        job.resultado = {
            "exito": exitos,
            "errores": errores,
            "total": job.total,
            "tiempo_total": round(job.duracion_seg(), 1),
            "raiz": str(raiz),
        }
        job.agregar_evento({
            "tipo": "fin",
            **job.resultado,
        })

    except Exception as e:
        job.estado = "error"
        from datetime import datetime as _dt
        job.fin = _dt.now()
        job.agregar_evento({"tipo": "error", "mensaje": str(e)})
    finally:
        # Marcar el fin de la cola
        try:
            job.cola.put_nowait(None)
        except Exception:
            pass


@app.post("/agent/generate")
async def endpoint_agent_generate(
    req: ExecuteRequest,
    usuario: str = Depends(obtener_usuario_actual),
):
    """
    Lanza la generación de código en background.
    Devuelve job_id para consultar el progreso por SSE.
    """
    if not req.autorizado:
        raise HTTPException(status_code=400, detail="Debes autorizar la ejecución")

    total = len(req.plan.estructura.archivos)
    job = job_manager.crear_job(req.plan.estructura.nombre_proyecto, total)

    # Lanzar la tarea en background
    asyncio.create_task(_ejecutar_generacion(job, req.plan))

    return {
        "job_id": job.job_id,
        "nombre": job.nombre_proyecto,
        "total": total,
    }


@app.get("/agent/stream/{job_id}")
async def endpoint_agent_stream(
    job_id: str,
    usuario: str = Depends(obtener_usuario_actual),
):
    """SSE con el progreso en vivo."""
    job = job_manager.obtener_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")

    async def event_generator():
        # Primero, reenviar eventos ya generados (por si se reconectó)
        for ev in job.eventos:
            yield f"data: {_json.dumps(ev, ensure_ascii=False)}\n\n"

        # Si ya terminó, cerrar
        if job.estado in ("terminado", "error"):
            yield "data: {\"tipo\":\"cerrado\"}\n\n"
            return

        # Esperar eventos nuevos
        while True:
            try:
                evento = await asyncio.wait_for(job.cola.get(), timeout=60)
            except asyncio.TimeoutError:
                yield ": ping\n\n"
                continue

            if evento is None:
                yield "data: {\"tipo\":\"cerrado\"}\n\n"
                break
            yield f"data: {_json.dumps(evento, ensure_ascii=False)}\n\n"

    return _SR(event_generator(), media_type="text/event-stream")


@app.get("/agent/status/{job_id}")
def endpoint_agent_status(
    job_id: str,
    usuario: str = Depends(obtener_usuario_actual),
):
    """Estado actual del job (fallback si se corta el SSE)."""
    job = job_manager.obtener_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    return {
        "job_id": job.job_id,
        "nombre": job.nombre_proyecto,
        "estado": job.estado,
        "actual": job.actual,
        "total": job.total,
        "duracion": round(job.duracion_seg(), 1),
        "resultado": job.resultado,
        "eventos": job.eventos[-20:],
    }


@app.get("/agent/projects")
def endpoint_listar_proyectos_generados(
    usuario: str = Depends(obtener_usuario_actual),
):
    """Lista los proyectos generados en disco."""
    return {"proyectos": listar_proyectos_generados()}


@app.delete("/agent/projects/{nombre}")
def endpoint_eliminar_proyecto_generado(
    nombre: str,
    usuario: str = Depends(obtener_usuario_actual),
):
    """Elimina un proyecto generado."""
    if not eliminar_proyecto(nombre):
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return {"status": "ok"}


# ===== AGENT DEV: FASE C (Validación + Corrección) =====

from src.agent_dev.tester import validar_proyecto
from src.agent_dev.file_writer import GENERATED_DIR


async def _ejecutar_validacion(job, plan: PlanCompleto, nombre_proyecto: str):
    """Corrutina que valida el proyecto generado."""
    from src.agent_dev.job_manager import job_manager
    import asyncio

    try:
        job.estado = "validando"

        raiz = GENERATED_DIR / nombre_proyecto
        if not raiz.exists():
            job.agregar_evento({
                "tipo": "error",
                "mensaje": f"Proyecto no encontrado: {nombre_proyecto}",
            })
            job.estado = "error"
            return

        job.agregar_evento({
            "tipo": "validacion_inicio",
            "job_id": job.job_id,
            "nombre": nombre_proyecto,
            "comandos_totales": (
                len(plan.estructura.comandos_setup)
                + len(plan.estructura.comandos_compilacion)
                + len(plan.estructura.comandos_tests)
            ),
        })

        # Callback para emitir eventos
        async def emitir(evento):
            job.agregar_evento(evento)
            # Si es autorización requerida, pausar hasta que llegue respuesta
            if evento.get("tipo") == "autorizacion_requerida":
                # Esperar respuesta del usuario
                try:
                    respuesta = await asyncio.wait_for(
                        job.cola_auth.get(), timeout=120
                    )
                    if respuesta.get("permitir"):
                        if respuesta.get("siempre"):
                            job.autorizaciones_sesion.add(evento["comando"])
                        # Emitir evento de autorizado
                        job.agregar_evento({
                            "tipo": "autorizacion_recibida",
                            "comando": evento["comando"],
                            "permitido": True,
                            "siempre": respuesta.get("siempre", False),
                        })
                    else:
                        job.agregar_evento({
                            "tipo": "autorizacion_recibida",
                            "comando": evento["comando"],
                            "permitido": False,
                        })
                except asyncio.TimeoutError:
                    job.agregar_evento({
                        "tipo": "autorizacion_timeout",
                        "comando": evento["comando"],
                    })

        # Ejecutar validación
        resumen = await validar_proyecto(
            plan, raiz, job.autorizaciones_sesion, emitir
        )

        job.estado = "terminado"
        from datetime import datetime as _dt
        job.fin = _dt.now()
        job.resultado = resumen

        job.agregar_evento({
            "tipo": "validacion_fin",
            **resumen,
            "tiempo_total": round(job.duracion_seg(), 1),
        })

    except Exception as e:
        job.estado = "error"
        from datetime import datetime as _dt
        job.fin = _dt.now()
        job.agregar_evento({"tipo": "error", "mensaje": str(e)})
    finally:
        try:
            job.cola.put_nowait(None)
        except Exception:
            pass


class ValidateRequest(BaseModel):
    plan: PlanCompleto
    nombre_proyecto: str


class AuthorizeRequest(BaseModel):
    comando: str
    permitir: bool
    siempre: bool = False


@app.post("/agent/validate")
async def endpoint_agent_validate(
    req: ValidateRequest,
    usuario: str = Depends(obtener_usuario_actual),
):
    """
    Lanza la validación (compilación + tests + corrección automática)
    de un proyecto ya generado.
    """
    raiz = GENERATED_DIR / req.nombre_proyecto
    if not raiz.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Proyecto no encontrado: {req.nombre_proyecto}",
        )

    total_comandos = (
        len(req.plan.estructura.comandos_setup)
        + len(req.plan.estructura.comandos_compilacion)
        + len(req.plan.estructura.comandos_tests)
    )
    job = job_manager.crear_job(req.nombre_proyecto, total_comandos)

    # Lanzar en background
    asyncio.create_task(_ejecutar_validacion(job, req.plan, req.nombre_proyecto))

    return {
        "job_id": job.job_id,
        "nombre": req.nombre_proyecto,
        "comandos_totales": total_comandos,
    }


@app.post("/agent/authorize/{job_id}")
async def endpoint_agent_authorize(
    job_id: str,
    req: AuthorizeRequest,
    usuario: str = Depends(obtener_usuario_actual),
):
    """
    Responde a una solicitud de autorización de comando bloqueado.
    """
    job = job_manager.obtener_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")

    try:
        job.cola_auth.put_nowait({
            "comando": req.comando,
            "permitir": req.permitir,
            "siempre": req.siempre,
        })
    except asyncio.QueueFull:
        raise HTTPException(status_code=429, detail="Cola de autorización llena")

    return {"status": "ok", "comando": req.comando, "permitido": req.permitir}
