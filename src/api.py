# src/api.py
import uuid
import sqlite3
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, PlainTextResponse
from pydantic import BaseModel

from src.core import niah
from src.core.history import (
    init_db, crear_proyecto, listar_proyectos, eliminar_proyecto,
    crear_chat, listar_chats, eliminar_chat,
    obtener_historial, limpiar_historial, guardar_mensaje,
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

app = FastAPI(title="NIAH API", version="9.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== CHECK DE DEPENDENCIAS AL ARRANQUE =====
def _check_deps():
    """Avisa en consola si falta algo para exportar a PDF/DOCX/XLSX/PPTX."""
    import shutil

    faltantes = []

    # python-pptx (PowerPoint)
    try:
        from pptx import Presentation  # noqa
    except ImportError:
        faltantes.append("python-pptx   →  pip install python-pptx")

    # weasyprint (PDF)
    try:
        import weasyprint  # noqa
    except ImportError:
        faltantes.append("weasyprint   →  pip install weasyprint")

    # python-docx (Word)
    try:
        import docx  # noqa
    except ImportError:
        faltantes.append("python-docx   →  pip install python-docx")

    # openpyxl (Excel)
    try:
        import openpyxl  # noqa
    except ImportError:
        faltantes.append("openpyxl   →  pip install openpyxl")

    # libreoffice-impress (para que el USUARIO pueda abrir los .pptx)
    # Nota: no es necesario para generar, pero sí para verificar/convertir.
    if not shutil.which("libreoffice") and not shutil.which("soffice"):
        faltantes.append(
            "libreoffice   →  sudo apt install libreoffice-impress"
        )

    if faltantes:
        print("\n⚠️  DEPENDENCIAS DE EXPORTACIÓN FALTANTES:")
        for f in faltantes:
            print(f"   - {f}")
        print()
    else:
        print("✅ Dependencias de exportación OK\n")


_check_deps()


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
    project_id_nuevo = str(uuid.uuid4())[:8]
    project_id_db = crear_proyecto(
        project_id_nuevo, usuario, req.nombre, req.tipo, origen="manual"
    )

    if project_id_db != project_id_nuevo:
        chats_existentes = listar_chats(project_id_db)
        chat_id = chats_existentes[0]["id"] if chats_existentes else None
        return {
            "project_id": project_id_db,
            "chat_id": chat_id,
            "resultado": f"Proyecto '{req.nombre}' ya existía, reutilizado",
            "reutilizado": True,
        }

    resultado = crear_estructura_proyecto(req.nombre, req.tipo)
    chat_id = str(uuid.uuid4())[:8]
    crear_chat(chat_id, project_id_db, "Chat inicial")
    return {
        "project_id": project_id_db,
        "chat_id": chat_id,
        "resultado": resultado,
        "reutilizado": False,
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


@app.get("/projects/{project_id}/documents/{nombre}/content")
def endpoint_documento_content(
    project_id: str,
    nombre: str,
    usuario: str = Depends(obtener_usuario_actual),
):
    """Devuelve el texto legible de un documento subido (PDF/TXT/CSV/etc)."""
    from pathlib import Path as _P
    from src.rag.indexer import DOCS_DIR, leer_documento

    if not verificar_propietario(project_id, usuario):
        raise HTTPException(status_code=403, detail="No tienes permiso")

    # Sanitizar el nombre para evitar path traversal
    nombre_seguro = _P(nombre).name
    archivo = DOCS_DIR / project_id / nombre_seguro
    if not archivo.exists() or not archivo.is_file():
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    try:
        contenido = leer_documento(archivo)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error leyendo documento: {e}")

    # Truncar si es enorme para no saturar el navegador
    max_chars = 200_000
    truncado = False
    if len(contenido) > max_chars:
        contenido = contenido[:max_chars]
        truncado = True

    return {
        "nombre": nombre_seguro,
        "contenido": contenido,
        "truncado": truncado,
        "bytes": archivo.stat().st_size,
    }


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


# ===== EXPORTAR MENSAJE INDIVIDUAL =====

class ExportMessageRequest(BaseModel):
    chat_id: str
    mensaje_idx: int = -1
    formato: str


@app.post("/agent/export-message")
def endpoint_export_message(
    req: ExportMessageRequest,
    usuario: str = Depends(obtener_usuario_actual),
):
    """Exporta una respuesta a MD/PDF/DOCX/XLSX/PPTX/HTML/TXT/JSON con diseño."""
    from fastapi.responses import Response as _R
    from src.ai_exporter import exportar_con_diseno

    if not verificar_chat_propietario(req.chat_id, usuario):
        raise HTTPException(status_code=403, detail="No tienes permiso")

    historial = obtener_historial(req.chat_id, limit=1000)
    if not historial:
        raise HTTPException(status_code=404, detail="Chat vacío")

    try:
        msg = historial[req.mensaje_idx]
    except IndexError:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")

    contenido = msg.get("content", "")
    if not contenido.strip():
        raise HTTPException(status_code=400, detail="Mensaje vacío")

    # Título: primera línea no vacía del mensaje
    primera = next(
        (l.strip("# ").strip() for l in contenido.split("\n") if l.strip()),
        "Respuesta de NIAH",
    )
    titulo = primera[:80] if primera else "Respuesta de NIAH"

    # Subtítulo: título del chat
    subtitulo = ""
    try:
        conn = sqlite3.connect("niah_history.db")
        c = conn.cursor()
        c.execute("SELECT titulo FROM chats WHERE id = ?", (req.chat_id,))
        row = c.fetchone()
        conn.close()
        if row and row[0]:
            subtitulo = row[0]
    except Exception:
        pass

    try:
        data, mime, ext = exportar_con_diseno(
            req.formato, titulo, contenido, subtitulo=subtitulo
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Dependencia faltante: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando {req.formato}: {e}")

    timestamp = int(datetime.now().timestamp() * 1000)
    return _R(
        content=data,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="respuesta_{timestamp}.{ext}"'
        },
    )


# ===== AGENT DEV: imports compartidos =====

from src.agent_dev.analyzer import generar_plan_completo
from src.agent_dev.schemas import AnalyzeRequest, PlanCompleto, ExecuteRequest
from src.agent_dev.coder import generar_archivo
from src.agent_dev.file_writer import (
    crear_estructura, escribir_archivo, listar_proyectos_generados,
    eliminar_proyecto as eliminar_proyecto_generado, GENERATED_DIR,
)
from src.agent_dev.job_manager import job_manager
from src.agent_dev.tester import validar_proyecto
from src.agent_dev.process_manager import (
    process_manager, ejecutar_proceso, detener_proceso,
)
from src.agent_dev.editor import (
    analizar_cambio, previsualizar_cambios, aplicar_cambios, revertir_cambios,
)

import asyncio
import json as _json
from fastapi.responses import StreamingResponse as _SR


# ===== AGENT DEV: FASE A =====

@app.post("/agent/analyze", response_model=PlanCompleto)
def endpoint_agent_analyze(
    req: AnalyzeRequest,
    usuario: str = Depends(obtener_usuario_actual),
):
    try:
        plan = generar_plan_completo(req.brief, req.nombre_sugerido)
        return plan
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en análisis: {str(e)}")


# ===== AGENT DEV: FASE B =====

async def _ejecutar_generacion(job, plan: PlanCompleto):
    try:
        job.estado = "generando"
        job.agregar_evento({
            "tipo": "inicio",
            "job_id": job.job_id,
            "nombre": job.nombre_proyecto,
            "total": job.total,
        })

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

            resultado = await asyncio.to_thread(
                generar_archivo,
                plan,
                archivo.ruta,
                archivo.descripcion,
                archivos_previos,
            )

            if resultado["exito"]:
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
        try:
            job.cola.put_nowait(None)
        except Exception:
            pass


@app.post("/agent/generate")
async def endpoint_agent_generate(
    req: ExecuteRequest,
    usuario: str = Depends(obtener_usuario_actual),
):
    if not req.autorizado:
        raise HTTPException(status_code=400, detail="Debes autorizar la ejecución")

    total = len(req.plan.estructura.archivos)

    project_id_nuevo = str(uuid.uuid4())[:8]
    project_id_db = crear_proyecto(
        project_id_nuevo,
        usuario,
        req.plan.estructura.nombre_proyecto,
        req.plan.estructura.nombre_proyecto,
        origen="ia",
    )

    if project_id_db == project_id_nuevo:
        chat_id_db = str(uuid.uuid4())[:8]
        crear_chat(chat_id_db, project_id_db, "Chat del proyecto")

        if req.historial_conversacion:
            for msg in req.historial_conversacion:
                rol = msg.get("role", "user")
                contenido = msg.get("content", "")
                if contenido:
                    guardar_mensaje(
                        chat_id_db,
                        rol,
                        contenido,
                        "niah-refine" if rol == "assistant" else None,
                    )
    else:
        chats_existentes = listar_chats(project_id_db)
        chat_id_db = chats_existentes[0]["id"] if chats_existentes else None

    job = job_manager.crear_job(
        req.plan.estructura.nombre_proyecto,
        total,
        user_id=usuario,
        project_id_db=project_id_db,
    )

    asyncio.create_task(_ejecutar_generacion(job, req.plan))

    return {
        "job_id": job.job_id,
        "nombre": job.nombre_proyecto,
        "total": total,
        "project_id_db": project_id_db,
        "chat_id_db": chat_id_db,
        "reutilizado": project_id_db != project_id_nuevo,
    }


@app.get("/agent/stream/{job_id}")
async def endpoint_agent_stream(
    job_id: str,
    usuario: str = Depends(obtener_usuario_actual),
):
    job = job_manager.obtener_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")

    async def event_generator():
        for ev in job.eventos:
            yield f"data: {_json.dumps(ev, ensure_ascii=False)}\n\n"

        if job.estado in ("terminado", "error"):
            yield "data: {\"tipo\":\"cerrado\"}\n\n"
            return

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
    return {"proyectos": listar_proyectos_generados()}


@app.delete("/agent/projects/{nombre}")
def endpoint_eliminar_proyecto_generado(
    nombre: str,
    usuario: str = Depends(obtener_usuario_actual),
):
    if not eliminar_proyecto_generado(nombre):
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return {"status": "ok"}


# ===== AGENT DEV: Archivos del proyecto generado =====

@app.get("/agent/projects/{nombre}/files")
def endpoint_agent_project_files(
    nombre: str,
    usuario: str = Depends(obtener_usuario_actual),
):
    raiz = GENERATED_DIR / nombre
    if not raiz.exists():
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    archivos = []
    for f in sorted(raiz.rglob("*")):
        if f.is_file() and ".bak" not in str(f):
            try:
                rel = f.relative_to(raiz)
                archivos.append({
                    "ruta": str(rel),
                    "bytes": f.stat().st_size,
                })
            except ValueError:
                continue
    return {"archivos": archivos}


@app.get("/agent/projects/{nombre}/file")
def endpoint_agent_project_file_content(
    nombre: str,
    ruta: str,
    usuario: str = Depends(obtener_usuario_actual),
):
    from src.agent_dev.file_writer import validar_ruta, RutaInseguraError

    raiz = GENERATED_DIR / nombre
    if not raiz.exists():
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    try:
        ruta_segura = validar_ruta(ruta)
    except RutaInseguraError as e:
        raise HTTPException(status_code=400, detail=str(e))

    archivo = raiz / ruta_segura
    if not archivo.exists() or not archivo.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    try:
        contenido = archivo.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"ruta": ruta_segura, "contenido": contenido}


# ===== AGENT DEV: Acciones sobre proyecto generado =====

class ActionRequest(BaseModel):
    accion: str


@app.get("/agent/projects/{nombre}/info")
def endpoint_agent_project_info(
    nombre: str,
    usuario: str = Depends(obtener_usuario_actual),
):
    raiz = GENERATED_DIR / nombre
    if not raiz.exists():
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    archivos = []
    total_bytes = 0
    for f in sorted(raiz.rglob("*")):
        if f.is_file() and ".bak" not in str(f):
            try:
                rel = f.relative_to(raiz)
                size = f.stat().st_size
                total_bytes += size
                archivos.append({"ruta": str(rel), "bytes": size})
            except ValueError:
                continue

    return {
        "nombre": nombre,
        "ruta": str(raiz.resolve()),
        "carpeta_raiz": str(GENERATED_DIR.resolve()),
        "archivos": archivos,
        "total_archivos": len(archivos),
        "total_bytes": total_bytes,
    }


@app.post("/agent/projects/{nombre}/action")
async def endpoint_agent_project_action(
    nombre: str,
    req: ActionRequest,
    usuario: str = Depends(obtener_usuario_actual),
):
    from src.agent_dev.executor import ejecutar_comando, detectar_timeout

    raiz = GENERATED_DIR / nombre
    if not raiz.exists():
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    accion = req.accion
    comandos_map = {"compile": [], "setup": [], "test": []}

    if accion == "setup":
        if (raiz / "requirements.txt").exists():
            comandos_map["setup"].append("pip install -r requirements.txt")
        if (raiz / "package.json").exists():
            comandos_map["setup"].append("npm install")
        if not comandos_map["setup"]:
            return {"accion": "setup", "resultados": [], "exitos": 0, "total": 0,
                    "mensaje": "No hay dependencias que instalar"}

    if accion == "compile":
        if (raiz / "src").exists():
            comandos_map["compile"].append("python -m py_compile src/*.py")
        if (raiz / "main.py").exists():
            comandos_map["compile"].append("python -m py_compile main.py")
        if (raiz / "package.json").exists():
            comandos_map["compile"].append("npm run build")
        if not comandos_map["compile"]:
            return {"accion": "compile", "resultados": [], "exitos": 0, "total": 0,
                    "mensaje": "No hay nada que compilar"}

    if accion == "test":
        if (raiz / "requirements.txt").exists():
            comandos_map["test"].append("pip install -r requirements.txt")
        if (raiz / "package.json").exists():
            comandos_map["test"].append("npm install")
        if (raiz / "tests").exists():
            comandos_map["test"].append("python -m pytest tests/ -v")
        elif (raiz / "package.json").exists():
            comandos_map["test"].append("npm test")
        if not comandos_map["test"]:
            return {"accion": "test", "resultados": [], "exitos": 0, "total": 0,
                    "mensaje": "No hay tests para ejecutar"}

    if accion == "run":
        comandos_run = []
        if (raiz / "backend" / "main.py").exists():
            comandos_run.append(
                f"cd {raiz}/backend && pip install -r requirements.txt && uvicorn main:app --reload"
            )
        if (raiz / "frontend" / "package.json").exists():
            comandos_run.append(f"cd {raiz}/frontend && npm install && npm run dev")
        if (raiz / "main.py").exists():
            comandos_run.append(f"cd {raiz} && python main.py")
        if (raiz / "src" / "main.py").exists():
            comandos_run.append(f"cd {raiz} && python src/main.py")
        if (raiz / "package.json").exists() and not (raiz / "frontend").exists():
            comandos_run.append(f"cd {raiz} && npm install && npm start")
        if not comandos_run:
            comandos_run.append(f"cd {raiz} && ls -la")
        return {"accion": "run", "comandos": comandos_run,
                "nota": "Ejecuta estos comandos en tu terminal."}

    if accion not in comandos_map:
        raise HTTPException(status_code=400, detail=f"Acción no soportada: {accion}")

    resultados = []
    for cmd in comandos_map[accion]:
        timeout = detectar_timeout(cmd)
        resultado = await ejecutar_comando(cmd, raiz, timeout=timeout)
        resultados.append(resultado)

    return {
        "accion": accion,
        "resultados": resultados,
        "exitos": sum(1 for r in resultados if r["exito"]),
        "total": len(resultados),
    }


# ===== AGENT DEV: Ejecutar proyecto en background =====

class RunRequest(BaseModel):
    comando: Optional[str] = None
    timeout: int = 300


def _detectar_comando_run(raiz) -> str:
    if (raiz / "backend" / "main.py").exists():
        return (
            "pip install -r backend/requirements.txt 2>/dev/null; "
            "cd backend && uvicorn main:app --host 0.0.0.0 --port 8000"
        )
    if (raiz / "frontend" / "package.json").exists():
        return "cd frontend && npm install 2>/dev/null; npm run dev"
    if (raiz / "package.json").exists():
        return "npm install 2>/dev/null; npm start"
    if (raiz / "main.py").exists():
        return "pip install -r requirements.txt 2>/dev/null; python main.py"
    if (raiz / "src" / "main.py").exists():
        return "cd src && python main.py"
    # Buscar cualquier .py en src/ con función main
    src_dir = raiz / "src"
    if src_dir.exists():
        for py in src_dir.glob("*.py"):
            try:
                contenido = py.read_text(encoding="utf-8", errors="replace")
                if '__name__ == "__main__"' in contenido or "def main(" in contenido:
                    return f"cd src && python {py.name}"
            except Exception:
                continue
    py_files = list(raiz.glob("*.py"))
    if py_files:
        return f"python {py_files[0].name}"
    return "ls -la"


@app.post("/agent/projects/{nombre}/run")
async def endpoint_agent_project_run(
    nombre: str,
    req: RunRequest,
    usuario: str = Depends(obtener_usuario_actual),
):
    from src.agent_dev.executor import analizar_comando

    raiz = GENERATED_DIR / nombre
    if not raiz.exists():
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    comando = req.comando or _detectar_comando_run(raiz)

    analisis = analizar_comando(comando)
    if analisis["accion"] == "bloqueado":
        raise HTTPException(status_code=400, detail=f"Bloqueado: {analisis['razon']}")

    proceso = process_manager.crear(nombre, comando, raiz)
    process_manager.limpiar_viejos(max_procesos=10)

    asyncio.create_task(ejecutar_proceso(proceso, timeout_segundos=req.timeout))

    return {
        "run_id": proceso.run_id,
        "comando": comando,
        "cwd": str(raiz),
        "timeout": req.timeout,
    }


@app.get("/agent/projects/{nombre}/run/{run_id}/log")
async def endpoint_agent_project_run_log(
    nombre: str,
    run_id: str,
    usuario: str = Depends(obtener_usuario_actual),
):
    proceso = process_manager.obtener(run_id)
    if not proceso:
        raise HTTPException(status_code=404, detail="Proceso no encontrado")

    async def event_generator():
        for linea in proceso.log:
            yield f"data: {_json.dumps({'tipo': 'linea', 'texto': linea}, ensure_ascii=False)}\n\n"

        if proceso.url_detectada:
            yield f"data: {_json.dumps({'tipo': 'url_detectada', 'url': proceso.url_detectada}, ensure_ascii=False)}\n\n"

        if proceso.estado in ("terminado", "error", "detenido"):
            yield f"data: {_json.dumps({'tipo': 'fin', 'estado': proceso.estado, 'exit_code': proceso.exit_code}, ensure_ascii=False)}\n\n"
            yield "data: {\"tipo\":\"cerrado\"}\n\n"
            return

        while True:
            try:
                evento = await asyncio.wait_for(proceso.cola.get(), timeout=60)
            except asyncio.TimeoutError:
                yield ": ping\n\n"
                continue

            if evento is None:
                yield f"data: {_json.dumps({'tipo': 'fin', 'estado': proceso.estado, 'exit_code': proceso.exit_code}, ensure_ascii=False)}\n\n"
                yield "data: {\"tipo\":\"cerrado\"}\n\n"
                break

            yield f"data: {_json.dumps(evento, ensure_ascii=False)}\n\n"

    return _SR(event_generator(), media_type="text/event-stream")


@app.get("/agent/projects/{nombre}/run/{run_id}/status")
def endpoint_agent_project_run_status(
    nombre: str,
    run_id: str,
    usuario: str = Depends(obtener_usuario_actual),
):
    proceso = process_manager.obtener(run_id)
    if not proceso:
        raise HTTPException(status_code=404, detail="Proceso no encontrado")
    return {
        "run_id": proceso.run_id,
        "estado": proceso.estado,
        "url_detectada": proceso.url_detectada,
        "exit_code": proceso.exit_code,
        "duracion": round(proceso.duracion_seg(), 1),
        "log": proceso.log[-50:],
    }


@app.delete("/agent/projects/{nombre}/run/{run_id}")
async def endpoint_agent_project_run_stop(
    nombre: str,
    run_id: str,
    usuario: str = Depends(obtener_usuario_actual),
):
    proceso = process_manager.obtener(run_id)
    if not proceso:
        raise HTTPException(status_code=404, detail="Proceso no encontrado")
    ok = await detener_proceso(proceso)
    return {"status": "ok" if ok else "no_proceso_activo"}


# ===== AGENT DEV: Fix automático =====

class FixRequest(BaseModel):
    archivo: str
    error: str


@app.post("/agent/projects/{nombre}/fix")
async def endpoint_agent_project_fix(
    nombre: str,
    req: FixRequest,
    usuario: str = Depends(obtener_usuario_actual),
):
    from src.agent_dev.file_writer import validar_ruta, RutaInseguraError
    from src.agent_dev.fixer import corregir_archivo

    raiz = GENERATED_DIR / nombre
    if not raiz.exists():
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    try:
        ruta_segura = validar_ruta(req.archivo)
    except RutaInseguraError as e:
        raise HTTPException(status_code=400, detail=str(e))

    archivo = raiz / ruta_segura
    if not archivo.exists() or not archivo.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    contenido_actual = archivo.read_text(encoding="utf-8", errors="replace")

    resultado = await asyncio.to_thread(
        corregir_archivo,
        archivo,
        contenido_actual,
        req.error,
        f"Proyecto: {nombre}",
    )

    if not resultado["exito"]:
        raise HTTPException(
            status_code=500,
            detail=f"El fixer no pudo corregir: {resultado['error']}",
        )

    backup = archivo.with_suffix(archivo.suffix + ".bak")
    if not backup.exists():
        backup.write_text(contenido_actual, encoding="utf-8")

    archivo.write_text(resultado["contenido_nuevo"], encoding="utf-8")

    return {
        "archivo": ruta_segura,
        "bytes_anteriores": len(contenido_actual.encode("utf-8")),
        "bytes_nuevos": len(resultado["contenido_nuevo"].encode("utf-8")),
        "modelo": resultado["modelo"],
        "contenido_nuevo": resultado["contenido_nuevo"][:500],
    }


@app.post("/agent/projects/{nombre}/open")
def endpoint_agent_project_open(
    nombre: str,
    usuario: str = Depends(obtener_usuario_actual),
):
    import subprocess
    import platform

    raiz = GENERATED_DIR / nombre
    if not raiz.exists():
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    try:
        sistema = platform.system()
        if sistema == "Linux":
            subprocess.Popen(["xdg-open", str(raiz)])
        elif sistema == "Darwin":
            subprocess.Popen(["open", str(raiz)])
        elif sistema == "Windows":
            subprocess.Popen(["explorer", str(raiz)])
        else:
            raise HTTPException(status_code=400, detail=f"Sistema no soportado: {sistema}")
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="No se encontró el comando para abrir el explorador",
        )

    return {"status": "ok", "ruta": str(raiz)}


# ===== AGENT DEV: Editor inteligente (análisis de impacto) =====

class EditAnalyzeRequest(BaseModel):
    instruccion: str


class EditApplyRequest(BaseModel):
    instruccion: str
    plan: dict
    autorizado: bool = False


class EditRevertRequest(BaseModel):
    backup_dir: str


@app.post("/agent/projects/{nombre}/edit/analyze")
async def endpoint_agent_project_edit_analyze(
    nombre: str,
    req: EditAnalyzeRequest,
    usuario: str = Depends(obtener_usuario_actual),
):
    """
    Analiza el impacto del cambio solicitado.
    NO modifica nada. Solo devuelve el plan de impacto.
    """
    raiz = GENERATED_DIR / nombre
    if not raiz.exists():
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    try:
        plan = await asyncio.to_thread(analizar_cambio, raiz, req.instruccion)
        return plan
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analizando: {str(e)}")


@app.post("/agent/projects/{nombre}/edit/apply")
async def endpoint_agent_project_edit_apply(
    nombre: str,
    req: EditApplyRequest,
    usuario: str = Depends(obtener_usuario_actual),
):
    """
    Aplica los cambios del plan (requiere autorización).
    """
    if not req.autorizado:
        raise HTTPException(status_code=400, detail="Debes autorizar los cambios")

    raiz = GENERATED_DIR / nombre
    if not raiz.exists():
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    try:
        # 1. Generar contenido nuevo de cada archivo
        preview = await asyncio.to_thread(
            previsualizar_cambios, raiz, req.plan, req.instruccion
        )

        # 2. Aplicar los cambios a disco
        resultado = await asyncio.to_thread(
            aplicar_cambios, raiz, preview["cambios"]
        )

        return {
            "exito": len(resultado["errores"]) == 0,
            "aplicados": resultado["aplicados"],
            "errores": resultado["errores"],
            "backup_dir": resultado["backup_dir"],
            "cambios_detalle": [
                {
                    "ruta": c["ruta"],
                    "accion": c.get("accion", "modificar"),
                    "bytes_nuevos": len(c.get("contenido_nuevo", "").encode("utf-8")),
                    "contenido_nuevo": c.get("contenido_nuevo", "")[:800],
                }
                for c in preview["cambios"]
                if c.get("exito")
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error aplicando: {str(e)}")


@app.post("/agent/projects/{nombre}/edit/revert")
async def endpoint_agent_project_edit_revert(
    nombre: str,
    req: EditRevertRequest,
    usuario: str = Depends(obtener_usuario_actual),
):
    """Revierte los cambios usando un backup."""
    raiz = GENERATED_DIR / nombre
    if not raiz.exists():
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    try:
        resultado = await asyncio.to_thread(
            revertir_cambios, raiz, req.backup_dir
        )
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error revirtiendo: {str(e)}")


# ===== AGENT DEV: Guardar mensaje del sistema =====

class SystemMessageRequest(BaseModel):
    chat_id: str
    contenido: str


@app.post("/agent/system-message")
async def endpoint_agent_system_message(
    req: SystemMessageRequest,
    usuario: str = Depends(obtener_usuario_actual),
):
    if not verificar_chat_propietario(req.chat_id, usuario):
        raise HTTPException(status_code=403, detail="No tienes permiso")

    guardar_mensaje(
        req.chat_id,
        "system",
        req.contenido,
        "sistema",
    )
    return {"status": "ok"}
