# src/agent_dev/schemas.py
from typing import List, Optional
from pydantic import BaseModel, Field


class AnalisisBrief(BaseModel):
    """Resultado del análisis del brief del usuario."""
    objetivo: str = Field(..., description="Qué quiere lograr el usuario en 1-2 frases")
    tipo_proyecto: str = Field(..., description="web, api, fullstack, script, cli, móvil, otro")
    funcionalidades: List[str] = Field(default_factory=list, description="Lista de features clave")
    usuarios_objetivo: str = Field("", description="Quién usará la app")
    requiere_persistencia: bool = Field(False, description="¿Necesita base de datos?")
    requiere_auth: bool = Field(False, description="¿Necesita login?")
    complejidad: str = Field("media", description="baja, media, alta")
    notas_adicionales: str = Field("", description="Observaciones del análisis")


class StackRecomendado(BaseModel):
    """Stack tecnológico elegido por el agente."""
    frontend: Optional[str] = Field(None, description="Ej: React 18 + TypeScript + Vite")
    backend: Optional[str] = Field(None, description="Ej: FastAPI (Python 3.12)")
    base_datos: Optional[str] = Field(None, description="Ej: SQLite, PostgreSQL, ninguna")
    estilos: Optional[str] = Field(None, description="Ej: CSS Modules, Tailwind")
    testing: Optional[str] = Field(None, description="Ej: pytest + httpx")
    extras: List[str] = Field(default_factory=list, description="Librerías adicionales")
    justificacion: str = Field("", description="Por qué este stack es óptimo")
    alternativas_descartadas: List[str] = Field(
        default_factory=list, description="Otros stacks considerados y por qué no"
    )


class ArchivoPlan(BaseModel):
    """Un archivo a generar."""
    ruta: str = Field(..., description="Ruta relativa, ej: src/main.py")
    descripcion: str = Field(..., description="Qué contiene este archivo")


class EstructuraProyecto(BaseModel):
    """Estructura completa del proyecto."""
    nombre_proyecto: str = Field(..., description="Nombre en kebab-case")
    descripcion_repo: str = Field("", description="Descripción para el repo de GitHub")
    carpetas: List[str] = Field(default_factory=list, description="Carpetas a crear")
    archivos: List[ArchivoPlan] = Field(default_factory=list, description="Archivos a generar")
    comandos_setup: List[str] = Field(
        default_factory=list, description="Ej: pip install -r requirements.txt"
    )
    comandos_compilacion: List[str] = Field(
        default_factory=list, description="Ej: npm run build"
    )
    comandos_tests: List[str] = Field(
        default_factory=list, description="Ej: pytest -v"
    )


class PlanCompleto(BaseModel):
    """Plan completo que se muestra al usuario antes de aprobar."""
    analisis: AnalisisBrief
    stack: StackRecomendado
    estructura: EstructuraProyecto
    tiempo_estimado_min: int = Field(5, description="Tiempo estimado en minutos")
    advertencias: List[str] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    """Request del usuario pidiendo análisis."""
    brief: str = Field(..., min_length=10, description="Descripción del proyecto")
    nombre_sugerido: Optional[str] = Field(None, description="Nombre opcional para el proyecto")


class ExecuteRequest(BaseModel):
    """Request para ejecutar un plan ya aprobado."""
    plan: PlanCompleto
    autorizado: bool = Field(False, description="Debe ser True para ejecutar")
    historial_conversacion: List[dict] = Field(
        default_factory=list,
        description="Historial del chat con NIAH antes de aprobar el plan",
    )
