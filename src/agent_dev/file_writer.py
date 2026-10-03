# src/agent_dev/file_writer.py
"""Escritura segura de archivos generados por el agente."""
import re
from pathlib import Path
from typing import Optional


GENERATED_DIR = Path.home() / "mi-agente-llama" / "generated_projects"


class RutaInseguraError(Exception):
    pass


def validar_ruta(ruta_relativa: str) -> str:
    """
    Valida que una ruta sea segura (no salga de la carpeta raíz).
    Devuelve la ruta normalizada.
    """
    # Quitar espacios y comillas
    ruta = ruta_relativa.strip().strip('"').strip("'")

    # Bloquear rutas absolutas
    if ruta.startswith("/") or re.match(r"^[A-Za-z]:", ruta):
        raise RutaInseguraError(f"Ruta absoluta no permitida: {ruta}")

    # Bloquear intentos de salir con ../
    partes = Path(ruta).parts
    if ".." in partes:
        raise RutaInseguraError(f"Ruta con '..' no permitida: {ruta}")

    # Normalizar
    ruta = str(Path(ruta))
    return ruta


def crear_estructura(nombre_proyecto: str, carpetas: list) -> Path:
    """
    Crea la carpeta raíz del proyecto y sus subcarpetas.
    Devuelve la ruta raíz.
    """
    # Validar nombre del proyecto
    nombre_limpio = re.sub(r"[^a-z0-9-]", "-", nombre_proyecto.lower())
    if not nombre_limpio or nombre_limpio == "-":
        raise ValueError(f"Nombre de proyecto inválido: {nombre_proyecto}")

    raiz = GENERATED_DIR / nombre_limpio
    raiz.mkdir(parents=True, exist_ok=True)

    for carpeta in carpetas:
        try:
            carpeta_valida = validar_ruta(carpeta)
            (raiz / carpeta_valida).mkdir(parents=True, exist_ok=True)
        except RutaInseguraError:
            # Ignorar carpetas inseguras en lugar de fallar
            continue

    return raiz


def escribir_archivo(
    raiz: Path,
    ruta_relativa: str,
    contenido: str,
    sobreescribir: bool = False,
) -> dict:
    """
    Escribe un archivo en la ruta indicada.
    Si ya existe y sobreescribir=False, guarda backup con .bak.
    Devuelve dict con: ruta, bytes_escritos, backup, exito.
    """
    ruta_validada = validar_ruta(ruta_relativa)
    path = raiz / ruta_validada

    # Crear carpeta padre si no existe
    path.parent.mkdir(parents=True, exist_ok=True)

    backup = None
    if path.exists() and not sobreescribir:
        backup = str(path) + ".bak"
        path.rename(backup)

    path.write_text(contenido, encoding="utf-8")

    return {
        "ruta": str(path.relative_to(raiz)),
        "bytes": len(contenido.encode("utf-8")),
        "backup": backup,
        "exito": True,
    }


def listar_proyectos_generados() -> list:
    """Lista todos los proyectos generados."""
    if not GENERATED_DIR.exists():
        return []
    return [
        {"nombre": p.name, "ruta": str(p)}
        for p in sorted(GENERATED_DIR.iterdir())
        if p.is_dir()
    ]


def eliminar_proyecto(nombre: str) -> bool:
    """Elimina un proyecto generado."""
    import shutil
    raiz = GENERATED_DIR / nombre
    if raiz.exists() and raiz.is_dir():
        shutil.rmtree(raiz)
        return True
    return False
