# src/agent_dev/job_manager.py
"""Gestor de trabajos en curso con colas SSE."""
import asyncio
import uuid
from typing import Dict, List, Optional
from datetime import datetime


class Job:
    def __init__(self, job_id: str, nombre_proyecto: str, total_archivos: int):
        self.job_id = job_id
        self.nombre_proyecto = nombre_proyecto
        self.total = total_archivos
        self.actual = 0
        self.estado = "pendiente"  # pendiente, generando, terminado, error
        self.eventos: List[dict] = []
        self.cola: asyncio.Queue = asyncio.Queue()
        self.inicio = datetime.now()
        self.fin: Optional[datetime] = None
        self.resultado: Optional[dict] = None
        self.cancelado = False

    def agregar_evento(self, evento: dict):
        """Agrega un evento a la cola y a la lista."""
        self.eventos.append(evento)
        try:
            self.cola.put_nowait(evento)
        except asyncio.QueueFull:
            pass

    def duracion_seg(self) -> float:
        fin = self.fin or datetime.now()
        return (fin - self.inicio).total_seconds()


class JobManager:
    def __init__(self):
        self.jobs: Dict[str, Job] = {}

    def crear_job(self, nombre_proyecto: str, total_archivos: int) -> Job:
        job_id = str(uuid.uuid4())[:8]
        job = Job(job_id, nombre_proyecto, total_archivos)
        self.jobs[job_id] = job
        return job

    def obtener_job(self, job_id: str) -> Optional[Job]:
        return self.jobs.get(job_id)

    def limpiar_jobs_viejos(self, max_jobs: int = 20):
        """Elimina trabajos antiguos para no llenar memoria."""
        if len(self.jobs) <= max_jobs:
            return
        ordenados = sorted(
            self.jobs.values(), key=lambda j: j.inicio, reverse=True
        )
        for job in ordenados[max_jobs:]:
            del self.jobs[job.job_id]


# Instancia global
job_manager = JobManager()
