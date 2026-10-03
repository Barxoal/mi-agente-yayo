# src/agent_dev/github_pusher.py
"""Sube proyectos generados por NIAH a GitHub vía API REST + git CLI."""
import os
import subprocess
import asyncio
from pathlib import Path

import httpx


GITHUB_API = "https://api.github.com"


def _get_token() -> str:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN no configurado en .env")
    return token


def _get_user() -> str:
    user = os.getenv("GITHUB_USER")
    if not user:
        raise RuntimeError("GITHUB_USER no configurado en .env")
    return user


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def verificar_token() -> dict:
    """Devuelve info del usuario autenticado. Lanza si el token es inválido."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{GITHUB_API}/user", headers=_headers())
        r.raise_for_status()
        return r.json()


async def repo_existe(user: str, nombre: str) -> bool:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{GITHUB_API}/repos/{user}/{nombre}", headers=_headers())
        if r.status_code == 200:
            return True
        if r.status_code == 404:
            return False
        r.raise_for_status()
        return False
async def crear_repo(nombre: str, descripcion: str = "", privado: bool = True) -> dict:
    """Crea repo nuevo. Si ya existe (422), devuelve el existente."""
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            f"{GITHUB_API}/user/repos",
            headers=_headers(),
            json={
                "name": nombre,
                "description": descripcion,
                "private": privado,
                "auto_init": False,
            },
        )
        if r.status_code == 422:
            r2 = await client.get(
                f"{GITHUB_API}/repos/{_get_user()}/{nombre}", headers=_headers()
            )
            r2.raise_for_status()
            return r2.json()
        r.raise_for_status()
        return r.json()


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=90,
    )


def _inicializar_local(path: Path) -> None:
    """git init (si hace falta) + .gitignore + add + commit."""
    if not (path / ".git").exists():
        r = _run_git(["init", "-b", "main"], path)
        if r.returncode != 0:
            raise RuntimeError(f"git init falló: {r.stderr.strip()}")

    _run_git(["config", "user.name", "NIAH"], path)
    _run_git(["config", "user.email", "niah@local"], path)

    gi = path / ".gitignore"
    if not gi.exists():
        gi.write_text(
            "venv/\n.venv/\nnode_modules/\n__pycache__/\n*.pyc\n"
            ".env\n.env.*\n*.db\n*.bak*\n.DS_Store\n",
            encoding="utf-8",
        )

    _run_git(["add", "-A"], path)

    r = _run_git(["status", "--porcelain"], path)
    if r.stdout.strip():
        r = _run_git(["commit", "-m", "Initial commit from NIAH"], path)
        if r.returncode != 0 and "nothing to commit" not in (r.stdout + r.stderr):
            raise RuntimeError(f"git commit falló: {r.stderr.strip()}")

    _run_git(["branch", "-M", "main"], path)
def _push_con_token(path: Path, user: str, nombre: str) -> None:
    """Configura remote con token, hace push, y restaura remote limpio."""
    token = _get_token()
    url_con_token = f"https://x-access-token:{token}@github.com/{user}/{nombre}.git"
    url_limpia = f"https://github.com/{user}/{nombre}.git"

    try:
        r = _run_git(["remote", "get-url", "origin"], path)
        if r.returncode == 0:
            _run_git(["remote", "set-url", "origin", url_con_token], path)
        else:
            _run_git(["remote", "add", "origin", url_con_token], path)

        r = _run_git(["push", "-u", "origin", "main"], path)
        if r.returncode != 0:
            raise RuntimeError(f"git push falló: {r.stderr.strip()}")
    finally:
        # Restaurar URL sin token SIEMPRE (aunque falle el push)
        _run_git(["remote", "set-url", "origin", url_limpia], path)


async def subir_proyecto(
    ruta_proyecto: Path,
    nombre_repo: str,
    descripcion: str = "",
    privado: bool = True,
) -> dict:
    """Flujo completo: crear repo (si no existe) + init local + push."""
    if not ruta_proyecto.exists() or not ruta_proyecto.is_dir():
        raise FileNotFoundError(f"Proyecto no encontrado: {ruta_proyecto}")

    # Sanitizar nombre (GitHub no acepta espacios ni caracteres raros)
    nombre_repo = nombre_repo.strip().replace(" ", "-")

    user = _get_user()

    existe = await repo_existe(user, nombre_repo)
    if not existe:
        repo_info = await crear_repo(nombre_repo, descripcion, privado)
        creado = True
    else:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{GITHUB_API}/repos/{user}/{nombre_repo}", headers=_headers()
            )
            r.raise_for_status()
            repo_info = r.json()
        creado = False

    # Trabajo bloqueante en thread
    await asyncio.to_thread(_inicializar_local, ruta_proyecto)
    await asyncio.to_thread(_push_con_token, ruta_proyecto, user, nombre_repo)

    return {
        "ok": True,
        "creado": creado,
        "nombre": nombre_repo,
        "repo_url": repo_info.get("html_url"),
        "clone_url": repo_info.get("clone_url"),
        "ssh_url": repo_info.get("ssh_url"),
        "privado": repo_info.get("private", privado),
    }

