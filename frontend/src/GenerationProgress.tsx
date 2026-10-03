import { useState, useEffect } from "react";
import {
  X,
  Loader2,
  Check,
  AlertCircle,
  FileCode,
  FolderOpen,
  Hammer,
  Wand2,
} from "lucide-react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

import { notificar } from "./notifications";

interface ArchivoEvento {
  i: number;
  total: number;
  ruta: string;
  estado: "generando" | "ok" | "error" | "error_escritura";
  modelo?: string;
  bytes?: number;
  tiempo?: number;
  error?: string;
}

interface Props {
  token: string;
  plan: any;
  historial: { role: string; content: string }[];
  nombreProyecto: string;
  onClose: () => void;
  onGenerated: () => void;
}

export default function GenerationProgress({
  token,
  plan,
  historial,
  nombreProyecto,
  onClose,
  onGenerated,
}: Props) {
  const [jobId, setJobId] = useState<string>("");
  const [archivos, setArchivos] = useState<ArchivoEvento[]>([]);
  const [estado, setEstado] = useState<
    "iniciando" | "generando" | "terminado" | "error"
  >("iniciando");
  const [resultado, setResultado] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const lanzar = async () => {
      try {
        const r = await fetch(`${API_URL}/agent/generate`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            plan,
            autorizado: true,
            historial_conversacion: historial,
          }),
        });

        if (!r.ok) {
          const data = await r.json().catch(() => ({}));
          setError(data.detail || "Error al iniciar la generación");
          setEstado("error");
          return;
        }

        const data = await r.json();
        setJobId(data.job_id);
        setEstado("generando");
      } catch {
        setError("Error de conexión con el servidor");
        setEstado("error");
      }
    };
    lanzar();
  }, []);

  // Notificación del SO al terminar la generación
  useEffect(() => {
    if (estado === "terminado") {
      notificar({
        titulo: "✅ Generación completa",
        cuerpo: `Proyecto "${nombreProyecto}" generado. ${archivos.filter((a) => a.estado === "ok").length} archivos.`,
        tag: `niah-gen-${nombreProyecto}`,
      });
    } else if (estado === "error") {
      notificar({
        titulo: "❌ Error en la generación",
        cuerpo: `El proyecto "${nombreProyecto}" no se pudo generar.`,
        tag: `niah-gen-${nombreProyecto}`,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [estado]);


  useEffect(() => {
    if (!jobId) return;

    const controller = new AbortController();
    let cancelado = false;

    const procesarEvento = (ev: any) => {
      if (ev.tipo === "archivo") {
        setArchivos((prev) => {
          const idx = prev.findIndex((a) => a.ruta === ev.ruta);
          if (idx === -1) return [...prev, ev];
          const copia = [...prev];
          copia[idx] = { ...copia[idx], ...ev };
          return copia;
        });
      } else if (ev.tipo === "fin") {
        setEstado("terminado");
        setResultado(ev);
        onGenerated();
      } else if (ev.tipo === "error") {
        setError(ev.mensaje || "Error durante la generación");
        setEstado("error");
      }
    };

    const conectar = async () => {
      try {
        const r = await fetch(`${API_URL}/agent/stream/${jobId}`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        });
        const reader = r.body?.getReader();
        if (!reader) return;
        const decoder = new TextDecoder();
        let buffer = "";

        while (!cancelado) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lineas = buffer.split("\n\n");
          buffer = lineas.pop() || "";

          for (const linea of lineas) {
            if (!linea.startsWith("data: ")) continue;
            const json = linea.slice(6).trim();
            if (!json) continue;
            try {
              procesarEvento(JSON.parse(json));
            } catch {}
          }
        }
      } catch (e: any) {
        if (e.name !== "AbortError") {
          console.error("Error en SSE:", e);
        }
      }
    };

    conectar();

    return () => {
      cancelado = true;
      controller.abort();
    };
  }, [jobId]);

  const totalArchivos = plan.estructura.archivos.length;
  const archivosOk = archivos.filter((a) => a.estado === "ok").length;
  const progreso = totalArchivos > 0 ? (archivosOk / totalArchivos) * 100 : 0;

  return (
    <div className="modal-overlay">
      <div
        className="modal modal-wide modal-progress"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-title">
          <Wand2 size={22} />
          <h3>Generando: {nombreProyecto}</h3>
          {estado === "terminado" && (
            <button className="modal-close" onClick={onClose}>
              <X size={16} />
            </button>
          )}
        </div>

        {estado === "iniciando" && (
          <div className="progress-loading">
            <Loader2 size={24} className="spin" />
            <p>Iniciando generación de código...</p>
          </div>
        )}

        {(estado === "generando" || estado === "terminado") && (
          <>
            <div className="progress-bar-container">
              <div
                className="progress-bar-fill"
                style={{ width: `${progreso}%` }}
              />
            </div>
            <p className="progress-text">
              {archivosOk} / {totalArchivos} archivos generados
              {estado === "terminado" && " ✅"}
            </p>

            <div className="progress-files">
              {plan.estructura.archivos.map((a: any) => {
                const ev = archivos.find((x) => x.ruta === a.ruta);
                const estadoArchivo = ev?.estado || "pendiente";
                return (
                  <div key={a.ruta} className={`progress-file ${estadoArchivo}`}>
                    <div className="progress-file-icon">
                      {estadoArchivo === "ok" ? (
                        <Check size={13} />
                      ) : estadoArchivo === "generando" ? (
                        <Loader2 size={13} className="spin" />
                      ) : estadoArchivo === "error" ||
                        estadoArchivo === "error_escritura" ? (
                        <AlertCircle size={13} />
                      ) : (
                        <FileCode size={13} />
                      )}
                    </div>
                    <div className="progress-file-body">
                      <code>{a.ruta}</code>
                      {ev?.modelo && (
                        <span className="progress-file-modelo">
                          {ev.modelo}
                        </span>
                      )}
                    </div>
                    {ev?.bytes !== undefined && (
                      <span className="progress-file-bytes">
                        {(ev.bytes / 1024).toFixed(1)} KB
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </>
        )}

        {estado === "terminado" && resultado && (
          <div className="progress-resultado">
            <div className="progress-resultado-row">
              <Check size={14} />
              <span>
                {resultado.exito} archivos generados
                {resultado.errores > 0 && ` · ${resultado.errores} errores`}
              </span>
            </div>
            <div className="progress-resultado-row">
              <FolderOpen size={14} />
              <code>{resultado.raiz}</code>
            </div>
            <div className="progress-resultado-row">
              <Hammer size={14} />
              <span>{resultado.tiempo_total}s en total</span>
            </div>
          </div>
        )}

        {error && (
          <div className="progress-error">
            <AlertCircle size={16} />
            <p>{error}</p>
          </div>
        )}

        <div className="modal-actions">
          {estado === "terminado" && (
            <button className="primary" onClick={onClose}>
              <Check size={14} />
              <span>Cerrar</span>
            </button>
          )}
          {estado === "generando" && (
            <button disabled>
              <Loader2 size={14} className="spin" />
              <span>Generando...</span>
            </button>
          )}
          {estado === "error" && (
            <button onClick={onClose}>
              <X size={14} />
              <span>Cerrar</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
