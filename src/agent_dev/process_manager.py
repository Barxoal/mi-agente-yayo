# src/agent_dev/process_manager.py
"""
Gestor de procesos en background para ejecutar proyectos generados.
"""
import asyncio
import re
import signal
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class RunProcess:
    def __init__(self, run_id: str, nombre_proyecto: str, comando: str, cwd: Path):
        self.run_id = run_id
        self.nombre_proyecto = nombre_proyecto
        self.comando = comando
        self.cwd = cwd
        self.proceso: Optional[asyncio.subprocess.Process] = None
        self.log: List[str] = []
        self.cola: asyncio.Queue = asyncio.Queue()
        self.url_detectada: Optional[str] = None
        self.estado = "iniciando"  # iniciando, corriendo, terminado, error, detenido
        self.inicio = datetime.now()
        self.fin: Optional[datetime] = None
        self.exit_code: Optional[int] = None

    def agregar_linea(self, linea: str):
        self.log.append(linea)
        # Limitar a 5000 líneas
        if len(self.log) > 5000:
            self.log = self.log[-5000:]
        try:
            self.cola.put_nowait({"tipo": "linea", "texto": linea})
        except asyncio.QueueFull:
            pass

    def agregar_evento(self, evento: dict):
        # Solo va a la cola (SSE). No contamina el log con texto crudo.
        try:
            self.cola.put_nowait(evento)
        except asyncio.QueueFull:
            pass

    def duracion_seg(self) -> float:
        fin = self.fin or datetime.now()
        return (fin - self.inicio).total_seconds()


class ProcessManager:
    def __init__(self):
        self.procesos: Dict[str, RunProcess] = {}

    def crear(self, nombre_proyecto: str, comando: str, cwd: Path) -> RunProcess:
        run_id = str(uuid.uuid4())[:8]
        proc = RunProcess(run_id, nombre_proyecto, comando, cwd)
        self.procesos[run_id] = proc
        return proc

    def obtener(self, run_id: str) -> Optional[RunProcess]:
        return self.procesos.get(run_id)

    def eliminar(self, run_id: str):
        self.procesos.pop(run_id, None)

    def limpiar_viejos(self, max_procesos: int = 10):
        """Elimina procesos terminados antiguos."""
        terminados = [
            p for p in self.procesos.values()
            if p.estado in ("terminado", "error", "detenido")
        ]
        if len(terminados) <= max_procesos:
            return
        ordenados = sorted(terminados, key=lambda p: p.inicio, reverse=True)
        for p in ordenados[max_procesos:]:
            self.eliminar(p.run_id)


# Patrones para detectar URL en la salida
PATRONES_URL = [
    re.compile(r"(https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0)[:\d]*\S*)"),
    re.compile(r"Running on (https?://\S+)"),
    re.compile(r"Uvicorn running on (https?://\S+)"),
    re.compile(r"Local:\s+(https?://\S+)"),
    re.compile(r"Listening on (https?://\S+)"),
]


def detectar_url(linea: str) -> Optional[str]:
    """Detecta una URL en una línea de log."""
    for patron in PATRONES_URL:
        match = patron.search(linea)
        if match:
            url = match.group(1).rstrip(".,;")
            # Normalizar 0.0.0.0 → localhost
            url = url.replace("0.0.0.0", "localhost")
            return url
    return None


async def ejecutar_proceso(run: RunProcess, timeout_segundos: int = 300):
    """
    Corre el proceso en background, captura stdout/stderr y detecta URLs.
    Timeout máximo: 5 minutos por defecto.
    """
    try:
        run.estado = "corriendo"
        run.agregar_evento({
            "tipo": "inicio",
            "run_id": run.run_id,
            "comando": run.comando,
            "cwd": str(run.cwd),
        })

        # Lanzar proceso
        proc = await asyncio.create_subprocess_shell(
            run.comando,
            cwd=str(run.cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_IGN),
        )
        run.proceso = proc

        # Leer líneas en vivo
        async def leer_lineas():
            while True:
                linea_bytes = await proc.stdout.readline()
                if not linea_bytes:
                    break
                linea = linea_bytes.decode("utf-8", errors="replace").rstrip()
                run.agregar_linea(linea)

                # Detectar URL
                if not run.url_detectada:
                    url = detectar_url(linea)
                    if url:
                        run.url_detectada = url
                        run.agregar_evento({
                            "tipo": "url_detectada",
                            "url": url,
                        })

        # Ejecutar con timeout
        try:
            await asyncio.wait_for(leer_lineas(), timeout=timeout_segundos)
            await proc.wait()
            run.exit_code = proc.returncode
            run.estado = "terminado" if proc.returncode == 0 else "error"
        except asyncio.TimeoutError:
            run.agregar_evento({
                "tipo": "timeout",
                "mensaje": f"Timeout de {timeout_segundos}s alcanzado",
            })
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
            run.exit_code = -1
            run.estado = "terminado"

    except Exception as e:
        run.agregar_evento({"tipo": "error", "mensaje": str(e)})
        run.estado = "error"
    finally:
        run.fin = datetime.now()
        try:
            run.cola.put_nowait(None)
        except Exception:
            pass


async def detener_proceso(run: RunProcess) -> bool:
    """Detiene el proceso asociado."""
    if not run.proceso or run.proceso.returncode is not None:
        return False
    try:
        run.proceso.terminate()
        try:
            await asyncio.wait_for(run.proceso.wait(), timeout=5)
        except asyncio.TimeoutError:
            run.proceso.kill()
            await run.proceso.wait()
        run.estado = "detenido"
        run.fin = datetime.now()
        run.agregar_evento({"tipo": "detenido", "mensaje": "Proceso detenido por el usuario"})
        try:
            run.cola.put_nowait(None)
        except Exception:
            pass
        return True
    except Exception as e:
        run.agregar_evento({"tipo": "error_detener", "mensaje": str(e)})
        return False


# Instancia global
process_manager = ProcessManager()
