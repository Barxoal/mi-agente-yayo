# src/agent_dev/editor.py
"""
Editor inteligente de proyectos: analiza cambios, detecta impacto y aplica
modificaciones con autorización del usuario.
"""
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import ollama


MODELO_ANALISIS = "qwen2.5:7b"
MODELO_CODIGO = "qwen2.5-coder:7b"

# Extensiones de código relevantes para analizar
EXT_CODIGO = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs",
    ".rb", ".php", ".cs", ".swift", ".kt", ".vue", ".svelte",
}
EXT_CONFIG = {".json", ".yaml", ".yml", ".toml", ".ini", ".env"}
EXT_DOCS = {".md", ".txt", ".rst"}
EXT_IGNORAR = {".bak", ".pyc", ".log", ".db", ".sqlite"}


def _extraer_json(texto: str) -> Optional[dict]:
    """Extrae el JSON de la respuesta del modelo."""
    inicio = texto.find("{")
    fin = texto.rfind("}")
    if inicio == -1 or fin == -1 or fin <= inicio:
        return None
    try:
        return json.loads(texto[inicio : fin + 1])
    except json.JSONDecodeError:
        return None


def _leer_archivos_proyecto(raiz: Path, limite_por_archivo: int = 3000) -> dict:
    """Lee todos los archivos de código del proyecto (limitado)."""
    archivos = {}
    for f in sorted(raiz.rglob("*")):
        if not f.is_file():
            continue
        if f.suffix in EXT_IGNORAR:
            continue
        if ".bak" in str(f) or ".git" in str(f).split("/"):
            continue
        if "__pycache__" in str(f) or "node_modules" in str(f):
            continue
        if f.suffix not in (EXT_CODIGO | EXT_CONFIG | EXT_DOCS):
            continue
        try:
            contenido = f.read_text(encoding="utf-8", errors="replace")
            rel = str(f.relative_to(raiz))
            if len(contenido) > limite_por_archivo:
                contenido = contenido[:limite_por_archivo] + "\n... (truncado)"
            archivos[rel] = contenido
        except Exception:
            continue
    return archivos


def _formatear_archivos(archivos: dict, limite_total: int = 15000) -> str:
    """Formatea los archivos para pasarlos al modelo."""
    lineas = []
    total = 0
    for ruta, contenido in archivos.items():
        bloque = f"\n=== {ruta} ===\n{contenido}\n"
        if total + len(bloque) > limite_total:
            lineas.append("\n... (más archivos truncados)\n")
            break
        lineas.append(bloque)
        total += len(bloque)
    return "".join(lineas)


# ============================================================
# FASE 1: Analizar el impacto del cambio
# ============================================================

PROMPT_ANALIZAR_CAMBIO = """Eres un arquitecto de software senior. El usuario quiere hacer un cambio en su proyecto y necesitas analizar su impacto.

INSTRUCCIÓN DEL USUARIO:
{instruccion}

ARCHIVOS DEL PROYECTO:
{archivos}

ANÁLISIS REQUERIDO:
1. Identifica TODOS los archivos que necesitan modificarse
2. Describe los cambios en cada uno (sin escribir el código completo, solo la idea)
3. Detecta dependencias afectadas (funciones, clases, imports, tests)
4. Evalúa el nivel de riesgo: "bajo", "medio" o "alto"
5. Si el riesgo es "medio" o "alto", propón ALTERNATIVAS que minimicen el impacto
6. Sugiere mejoras adicionales relacionadas (opcionales, no obligatorias)

Devuelve un JSON con:
{{
  "resumen": "descripción breve del cambio en 1-2 frases",
  "riesgo": "bajo" | "medio" | "alto",
  "razon_riesgo": "por qué ese nivel",
  "archivos": [
    {{
      "ruta": "src/main.py",
      "accion": "modificar" | "crear" | "eliminar",
      "descripcion": "qué cambiar exactamente",
      "afecta": ["función calcular", "test_main.py::test_calcular"]
    }}
  ],
  "dependencias_afectadas": ["lista de dependencias o tests que se romperían"],
  "alternativas": [
    {{
      "titulo": "Alternativa A",
      "descripcion": "cómo hacer el cambio sin romper X",
      "trade_off": "qué se pierde con esta alternativa"
    }}
  ],
  "sugerencias_extra": [
    {{
      "titulo": "Refactorizar X",
      "descripcion": "por qué sería buena idea"
    }}
  ]
}}

Responde ÚNICAMENTE con el JSON, sin markdown, sin texto extra.
"""


def analizar_cambio(raiz: Path, instruccion: str) -> dict:
    """
    Analiza el impacto del cambio solicitado.
    Devuelve un dict con: resumen, riesgo, archivos, alternativas, etc.
    """
    archivos = _leer_archivos_proyecto(raiz)
    archivos_str = _formatear_archivos(archivos)

    prompt = PROMPT_ANALIZAR_CAMBIO.format(
        instruccion=instruccion,
        archivos=archivos_str,
    )

    respuesta = ollama.chat(
        model=MODELO_ANALISIS,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.3, "num_predict": 2000},
        format="json",
    )

    datos = _extraer_json(respuesta["message"]["content"]) or {}

    # Normalizar
    return {
        "resumen": datos.get("resumen", instruccion),
        "riesgo": datos.get("riesgo", "medio"),
        "razon_riesgo": datos.get("razon_riesgo", ""),
        "archivos": datos.get("archivos", []),
        "dependencias_afectadas": datos.get("dependencias_afectadas", []),
        "alternativas": datos.get("alternativas", []),
        "sugerencias_extra": datos.get("sugerencias_extra", []),
    }


# ============================================================
# FASE 2: Generar el diff/código nuevo para cada archivo
# ============================================================

PROMPT_GENERAR_CAMBIO = """Eres un desarrollador senior. Debes modificar el archivo "{ruta}" para cumplir esta instrucción:

INSTRUCCIÓN: {instruccion}

DESCRIPCIÓN DEL CAMBIO EN ESTE ARCHIVO:
{descripcion}

CONTENIDO ACTUAL DEL ARCHIVO:
\"\"\"
{contenido_actual}
\"\"\"

CONTEXTO DEL PROYECTO (otros archivos):
{contexto}

TAREA:
Devuelve ÚNICAMENTE el contenido COMPLETO y FINAL del archivo después del cambio.
NO uses bloques de markdown.
NO incluyas explicaciones ni comentarios sobre lo que cambiaste.
Solo el código.

REGLAS:
1. Mantén el estilo y formato del archivo original
2. Corrige lo necesario para cumplir la instrucción
3. No rompas funcionalidad existente
4. Si necesitas importar algo nuevo, agrégalo

CONTENIDO FINAL DEL ARCHIVO:
"""


def _limpiar_markdown(texto: str) -> str:
    """Limpia bloques ``` si el modelo los agregó."""
    texto = texto.strip()
    if texto.startswith("```"):
        # Quitar primera línea (```python)
        lineas = texto.split("\n")
        if lineas[0].startswith("```"):
            lineas = lineas[1:]
        # Quitar última línea ```
        if lineas and lineas[-1].strip() == "```":
            lineas = lineas[:-1]
        texto = "\n".join(lineas)
    return texto


def generar_cambio_archivo(
    raiz: Path,
    ruta_relativa: str,
    descripcion: str,
    instruccion: str,
    archivos_contexto: dict,
) -> dict:
    """Genera el contenido nuevo de UN archivo."""
    archivo = raiz / ruta_relativa
    contenido_actual = ""
    if archivo.exists():
        contenido_actual = archivo.read_text(encoding="utf-8", errors="replace")

    # Preparar contexto (otros archivos, limitado)
    otros = {k: v for k, v in archivos_contexto.items() if k != ruta_relativa}
    contexto = _formatear_archivos(otros, limite_total=6000)

    prompt = PROMPT_GENERAR_CAMBIO.format(
        ruta=ruta_relativa,
        instruccion=instruccion,
        descripcion=descripcion,
        contenido_actual=contenido_actual[:4000],
        contexto=contexto,
    )

    try:
        respuesta = ollama.chat(
            model=MODELO_CODIGO,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.2, "num_predict": 4000},
        )
        contenido_nuevo = _limpiar_markdown(respuesta["message"]["content"])

        if not contenido_nuevo.strip():
            return {"exito": False, "error": "Contenido vacío", "ruta": ruta_relativa}

        return {
            "ruta": ruta_relativa,
            "contenido_anterior": contenido_actual,
            "contenido_nuevo": contenido_nuevo,
            "exito": True,
        }
    except Exception as e:
        return {"exito": False, "error": str(e), "ruta": ruta_relativa}


def previsualizar_cambios(raiz: Path, plan: dict, instruccion: str) -> dict:
    """
    Genera los cambios en memoria (sin escribir a disco).
    Devuelve un dict con el contenido nuevo de cada archivo.
    """
    archivos = _leer_archivos_proyecto(raiz)
    cambios = []

    for item in plan.get("archivos", []):
        ruta = item.get("ruta", "")
        accion = item.get("accion", "modificar")
        descripcion = item.get("descripcion", "")

        if not ruta:
            continue

        if accion == "eliminar":
            cambios.append({
                "ruta": ruta,
                "accion": "eliminar",
                "exito": True,
                "contenido_anterior": "",
                "contenido_nuevo": "",
            })
            continue

        # Generar contenido nuevo
        resultado = generar_cambio_archivo(
            raiz, ruta, descripcion, instruccion, archivos
        )
        resultado["accion"] = accion
        cambios.append(resultado)

    return {"cambios": cambios}


# ============================================================
# FASE 3: Aplicar los cambios (con backup)
# ============================================================

def aplicar_cambios(raiz: Path, cambios: list) -> dict:
    """
    Aplica los cambios al disco.
    Devuelve un dict con: aplicados, errores, backups.
    """
    aplicados = []
    errores = []
    backups = []

    # Backup completo antes de aplicar
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = raiz / f".edit_backup_{timestamp}"
    backup_dir.mkdir(exist_ok=True)

    for cambio in cambios:
        ruta = cambio.get("ruta", "")
        if not cambio.get("exito"):
            errores.append({"ruta": ruta, "error": cambio.get("error", "Fallo al generar")})
            continue

        archivo = raiz / ruta
        accion = cambio.get("accion", "modificar")

        try:
            # Backup del archivo existente
            if archivo.exists():
                backup_path = backup_dir / ruta.replace("/", "_")
                shutil.copy2(archivo, backup_path)
                backups.append(str(backup_path.relative_to(raiz)))

            if accion == "eliminar":
                if archivo.exists():
                    archivo.unlink()
                aplicados.append({"ruta": ruta, "accion": "eliminar"})
            else:
                # Crear carpeta padre si no existe
                archivo.parent.mkdir(parents=True, exist_ok=True)
                archivo.write_text(cambio["contenido_nuevo"], encoding="utf-8")
                aplicados.append({
                    "ruta": ruta,
                    "accion": accion,
                    "bytes": len(cambio["contenido_nuevo"].encode("utf-8")),
                })
        except Exception as e:
            errores.append({"ruta": ruta, "error": str(e)})

    return {
        "aplicados": aplicados,
        "errores": errores,
        "backup_dir": str(backup_dir.relative_to(raiz)),
    }


def revertir_cambios(raiz: Path, backup_dir: str) -> dict:
    """Revierte los cambios usando el backup."""
    backup_path = raiz / backup_dir
    if not backup_path.exists():
        return {"exito": False, "error": "Backup no encontrado"}

    revertidos = []
    for backup_file in backup_path.iterdir():
        if backup_file.is_file():
            # Reconstruir ruta original (los / se reemplazaron por _)
            nombre = backup_file.name
            # Buscar el archivo original probando con / en cada _
            partes = nombre.split("_", 1)
            if len(partes) == 2:
                ruta_original = nombre.replace("_", "/")
                archivo = raiz / ruta_original
                archivo.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_file, archivo)
                revertidos.append(ruta_original)

    return {"exito": True, "revertidos": revertidos}
