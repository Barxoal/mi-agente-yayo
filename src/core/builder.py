# src/core/builder.py
from pathlib import Path

PROJECTS_DIR = Path("projects")


def crear_estructura_proyecto(nombre: str, tipo: str = "python") -> str:
    """Crea un proyecto con estructura de carpetas y archivos base."""
    base = PROJECTS_DIR / nombre
    if base.exists():
        return f"El proyecto '{nombre}' ya existe en {base}"

    base.mkdir(parents=True, exist_ok=True)

    if tipo == "python":
        (base / "src").mkdir(exist_ok=True)
        (base / "tests").mkdir(exist_ok=True)
        (base / "src" / "__init__.py").write_text("")
        (base / "tests" / "__init__.py").write_text("")
        (base / "main.py").write_text(
            'def main():\n    print("Hola desde ' + nombre + '")\n\n\nif __name__ == "__main__":\n    main()\n'
        )
        (base / "requirements.txt").write_text("# Dependencias del proyecto\n")
        (base / "README.md").write_text(f"# {nombre}\n\nProyecto generado por NIAH.\n")

    elif tipo == "web":
        (base / "frontend").mkdir(exist_ok=True)
        (base / "backend").mkdir(exist_ok=True)
        (base / "frontend" / "index.html").write_text(
            f"<!DOCTYPE html>\n<html>\n<head><title>{nombre}</title></head>\n<body><h1>{nombre}</h1></body>\n</html>\n"
        )
        (base / "backend" / "app.py").write_text(
            'from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get("/")\ndef root():\n    return {"proyecto": "' + nombre + '"}\n'
        )
        (base / "README.md").write_text(f"# {nombre}\n\nProyecto web generado por NIAH.\n")

    elif tipo == "api":
        (base / "app").mkdir(exist_ok=True)
        (base / "app" / "__init__.py").write_text("")
        (base / "app" / "main.py").write_text(
            'from fastapi import FastAPI\n\napp = FastAPI(title="' + nombre + '")\n\n@app.get("/")\ndef root():\n    return {"status": "ok"}\n'
        )
        (base / "requirements.txt").write_text("fastapi\nuvicorn[standard]\n")
        (base / "README.md").write_text(f"# {nombre}\n\nAPI generada por NIAH.\n")

    else:  # script
        (base / "script.py").write_text('# Script generado por NIAH\nprint("Hola mundo")\n')
        (base / "README.md").write_text(f"# {nombre}\n\nScript generado por NIAH.\n")

    return f"Proyecto '{nombre}' creado en {base.resolve()}\n\nEstructura:\n" + _listar_estructura(base)


def _listar_estructura(path: Path, prefix: str = "") -> str:
    items = sorted(path.iterdir())
    lines = []
    for i, item in enumerate(items):
        is_last = i == len(items) - 1
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{item.name}")
        if item.is_dir():
            new_prefix = prefix + ("    " if is_last else "│   ")
            lines.append(_listar_estructura(item, new_prefix))
    return "\n".join(lines)


def listar_proyectos() -> str:
    if not PROJECTS_DIR.exists():
        return "No hay proyectos creados aún."
    proyectos = [p.name for p in PROJECTS_DIR.iterdir() if p.is_dir()]
    if not proyectos:
        return "No hay proyectos creados aún."
    return "Proyectos:\n" + "\n".join(f"  • {p}" for p in sorted(proyectos))
