# src/agent_dev/executor.py
"""
Ejecutor de comandos con lista blanca y autorización dinámica.
"""
import asyncio
import re
import shlex
from pathlib import Path
from typing import Optional


# ===== LISTA BLANCA (se ejecutan sin preguntar) =====
COMANDOS_PERMITIDOS = {
    "python", "python3", "pip", "pip3", "pytest",
    "node", "npm", "npx", "yarn", "pnpm",
    "ls", "cat", "echo", "pwd",
    "cargo", "rustc", "go",
    "mkdir", "touch",
}

# ===== LISTA NEGRA (siempre requieren autorización) =====
COMANDOS_PELIGROSOS = {
    "sudo", "rm", "rmdir", "mv", "cp",
    "curl", "wget", "ssh", "scp", "rsync",
    "chmod", "chown", "chgrp",
    "bash", "sh", "zsh", "fish",
    "kill", "killall", "pkill",
    "dd", "mkfs", "fdisk", "mount", "umount",
    "apt", "apt-get", "dpkg", "snap",
    "systemctl", "service", "reboot", "shutdown",
    "git",
}

# Caracteres que siempre requieren autorización
PATRONES_PELIGROSOS = [
    r">\s*/",
    r"rm\s+-rf",
    r";\s*sudo",
    r"&&\s*rm",
    r"\|\s*bash",
    r"\|\s*sh",
    r"\$\(",
    r"`",
]


class ComandoBloqueado(Exception):
    """Se lanza cuando un comando requiere autorización."""
    def __init__(self, comando: str, razon: str):
        self.comando = comando
        self.razon = razon
        super().__init__(f"{razon}: {comando}")


def analizar_comando(comando: str) -> dict:
    """
    Analiza un comando y decide:
    - permitido (lista blanca)
    - requiere_autorizacion (lista negra o desconocido)
    - bloqueado (patrones peligrosos irreversibles)
    """
    comando = comando.strip()
    if not comando:
        return {"accion": "bloqueado", "razon": "Comando vacío"}

    for patron in PATRONES_PELIGROSOS:
        if re.search(patron, comando):
            return {
                "accion": "requiere_autorizacion",
                "razon": f"Contiene patrón peligroso: {patron}",
            }

    try:
        partes = shlex.split(comando)
    except ValueError as e:
        return {"accion": "bloqueado", "razon": f"Comando malformado: {e}"}

    if not partes:
        return {"accion": "bloqueado", "razon": "Comando vacío"}

    primer_token = partes[0].split("/")[-1]
    if primer_token in COMANDOS_PELIGROSOS:
        return {
            "accion": "requiere_autorizacion",
            "razon": f"Comando de lista negra: {primer_token}",
        }

    comandos_encadenados = re.split(r"[&|;]", comando)
    for sub_cmd in comandos_encadenados:
        sub_cmd = sub_cmd.strip()
        if not sub_cmd:
            continue
        try:
            sub_partes = shlex.split(sub_cmd)
            if sub_partes:
                sub_token = sub_partes[0].split("/")[-1]
                if sub_token in COMANDOS_PELIGROSOS:
                    return {
                        "accion": "requiere_autorizacion",
                        "razon": f"Comando encadenado peligroso: {sub_token}",
                    }
                if sub_token not in COMANDOS_PERMITIDOS:
                    return {
                        "accion": "requiere_autorizacion",
                        "razon": f"Comando desconocido: {sub_token}",
                    }
        except ValueError:
            return {"accion": "bloqueado", "razon": "Comando encadenado malformado"}

    return {"accion": "permitido", "razon": "En lista blanca"}


async def ejecutar_comando(
    comando: str,
    cwd: Path,
    timeout: int = 30,
    autorizaciones_sesion: Optional[set] = None,
) -> dict:
    """
    Ejecuta un comando de forma segura.
    """
    autorizaciones_sesion = autorizaciones_sesion or set()

    analisis = analizar_comando(comando)

    if analisis["accion"] == "bloqueado":
        return {
            "comando": comando,
            "exit_code": -1,
            "stdout": "",
            "stderr": "",
            "tiempo": 0,
            "exito": False,
            "requiere_auth": False,
            "error": analisis["razon"],
        }

    if analisis["accion"] == "requiere_autorizacion":
        if comando in autorizaciones_sesion:
            pass
        else:
            return {
                "comando": comando,
                "exit_code": -1,
                "stdout": "",
                "stderr": "",
                "tiempo": 0,
                "exito": False,
                "requiere_auth": True,
                "razon_auth": analisis["razon"],
            }

    import time
    inicio = time.time()
    try:
        proceso = await asyncio.create_subprocess_shell(
            comando,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proceso.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proceso.kill()
            await proceso.wait()
            return {
                "comando": comando,
                "exit_code": -1,
                "stdout": "",
                "stderr": "",
                "tiempo": round(time.time() - inicio, 2),
                "exito": False,
                "requiere_auth": False,
                "error": f"Timeout después de {timeout}s",
            }

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        tiempo = round(time.time() - inicio, 2)

        return {
            "comando": comando,
            "exit_code": proceso.returncode,
            "stdout": stdout[-5000:],
            "stderr": stderr[-5000:],
            "tiempo": tiempo,
            "exito": proceso.returncode == 0,
            "requiere_auth": False,
            "error": (
                None
                if proceso.returncode == 0
                else (stderr.strip() or stdout.strip() or f"Exit code {proceso.returncode}")
            ),
        }

    except FileNotFoundError as e:
        return {
            "comando": comando,
            "exit_code": -1,
            "stdout": "",
            "stderr": "",
            "tiempo": round(time.time() - inicio, 2),
            "exito": False,
            "requiere_auth": False,
            "error": f"Ejecutable no encontrado: {e}",
        }
    except Exception as e:
        return {
            "comando": comando,
            "exit_code": -1,
            "stdout": "",
            "stderr": "",
            "tiempo": round(time.time() - inicio, 2),
            "exito": False,
            "requiere_auth": False,
            "error": str(e),
        }


def detectar_timeout(comando: str) -> int:
    """Timeouts inteligentes según el tipo de comando."""
    if "pip install" in comando or "npm install" in comando or "yarn install" in comando:
        return 300
    if "npm run build" in comando or "cargo build" in comando:
        return 180
    if "pytest" in comando or "npm test" in comando or "vitest" in comando:
        return 180
    if "py_compile" in comando:
        return 30
    return 30
