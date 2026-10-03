import { useState, useRef, useEffect } from "react";
import {
  X,
  Play,
  Square,
  Loader2,
  ExternalLink,
  Terminal,
  AlertCircle,
  Check,
  Copy,
} from "lucide-react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

import { notificar } from "./notifications";

interface Props {
  token: string;
  nombreProyecto: string;
  chatId: string;
  onClose: () => void;
  onFinalizado: (resumen: string) => void;
}

export default function RunModal({
  token,
  nombreProyecto,
  chatId,
  onClose,
  onFinalizado,
}: Props) {
  const [runId, setRunId] = useState<string | null>(null);
  const [comando, setComando] = useState<string>("");
  const [log, setLog] = useState<string[]>([]);
  const [estado, setEstado] = useState<
    "iniciando" | "corriendo" | "terminado" | "error" | "detenido"
  >("iniciando");
  const [urlDetectada, setUrlDetectada] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [copiado, setCopiado] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [log]);

  // Notificación del SO al terminar la ejecución
  useEffect(() => {
    if (estado === "terminado") {
      notificar({
        titulo: "✅ Ejecución completa",
        cuerpo: `Proyecto "${nombreProyecto}" terminó correctamente.${urlDetectada ? ` URL: ${urlDetectada}` : ""}`,
        tag: `niah-run-${nombreProyecto}`,
      });
    } else if (estado === "error") {
      notificar({
        titulo: "❌ Error en la ejecución",
        cuerpo: `"${nombreProyecto}" terminó con errores. Revisa el log.`,
        tag: `niah-run-${nombreProyecto}`,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [estado]);

  useEffect(() => {
    // Auto-lanzar al montar
    lanzar();
    return () => {
      // Cleanup: si hay proceso corriendo, no lo matamos automáticamente
      // (para que pueda seguir corriendo en background)
    };
  }, []);

  const lanzar = async () => {
    setLog([]);
    setEstado("iniciando");
    setError("");

    try {
      const r = await fetch(
        `${API_URL}/agent/projects/${nombreProyecto}/run`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ timeout: 600 }),
        }
      );

      if (!r.ok) {
        const data = await r.json().catch(() => ({}));
        setError(data.detail || "Error al iniciar el proceso");
        setEstado("error");
        return;
      }

      const data = await r.json();
      setRunId(data.run_id);
      setComando(data.comando);
      setEstado("corriendo");

      // Conectar SSE al log
      conectarSSE(data.run_id);
    } catch {
      setError("Error de conexión");
      setEstado("error");
    }
  };

  const conectarSSE = async (rid: string) => {
    const controller = new AbortController();
    let cancelado = false;

    try {
      const r = await fetch(
        `${API_URL}/agent/projects/${nombreProyecto}/run/${rid}/log`,
        {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        }
      );

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

  const procesarEvento = (ev: any) => {
    if (ev.tipo === "linea") {
      setLog((prev) => [...prev, ev.texto]);
    } else if (ev.tipo === "url_detectada") {
      setUrlDetectada(ev.url);
    } else if (ev.tipo === "fin") {
      setEstado(ev.estado === "terminado" ? "terminado" : ev.estado as any);
    } else if (ev.tipo === "detenido") {
      setEstado("detenido");
    } else if (ev.tipo === "error") {
      setError(ev.mensaje);
      setEstado("error");
    }
  };

  const detener = async () => {
    if (!runId) return;
    try {
      await fetch(
        `${API_URL}/agent/projects/${nombreProyecto}/run/${runId}`,
        {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      setEstado("detenido");
    } catch {}
  };

  const copiarComando = () => {
    navigator.clipboard.writeText(comando);
    setCopiado(true);
    setTimeout(() => setCopiado(false), 1500);
  };

  const cerrarYGuardar = async () => {
    // Si el proceso sigue corriendo, lo dejamos (o lo detenemos)
    if (estado === "corriendo" && runId) {
      if (!confirm("El proceso sigue corriendo. ¿Detenerlo antes de cerrar?")) {
        // El usuario quiere dejarlo corriendo
        onClose();
        return;
      }
      await detener();
    }

    // Guardar el resumen en el chat
    const resumen = construirResumen();
    if (resumen) {
      try {
        await fetch(`${API_URL}/agent/system-message`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            chat_id: chatId,
            contenido: resumen,
          }),
        });
        onFinalizado(resumen);
      } catch {}
    }

    onClose();
  };

  const construirResumen = (): string => {
    const partes: string[] = [];
    partes.push(`**Ejecución del proyecto** \`${nombreProyecto}\``);
    partes.push("");
    partes.push(`**Comando:** \`${comando}\``);
    partes.push(`**Estado:** ${estado}`);
    if (urlDetectada) {
      partes.push(`**URL:** ${urlDetectada}`);
    }

    // Últimas 10 líneas del log
    if (log.length > 0) {
      partes.push("");
      partes.push("**Últimas líneas del log:**");
      partes.push("```");
      partes.push(...log.slice(-10));
      partes.push("```");
    }

    return partes.join("\n");
  };

  return (
    <div className="modal-overlay" onClick={cerrarYGuardar}>
      <div
        className="modal modal-wide modal-run"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-title">
          <Terminal size={20} />
          <h3>Ejecutar: {nombreProyecto}</h3>
          <button className="modal-close" onClick={cerrarYGuardar}>
            <X size={16} />
          </button>
        </div>

        <div className="run-comando">
          <code>{comando}</code>
          <button className="btn-icon" onClick={copiarComando} title="Copiar">
            {copiado ? <Check size={13} /> : <Copy size={13} />}
          </button>
        </div>

        {urlDetectada && (
          <div className="run-url">
            <span>🌐 Servidor detectado:</span>
            <a href={urlDetectada} target="_blank" rel="noopener noreferrer">
              {urlDetectada}
              <ExternalLink size={12} />
            </a>
          </div>
        )}

        <div className="run-log" ref={logRef}>
          {log.length === 0 && estado === "iniciando" && (
            <div className="run-log-vacio">
              <Loader2 size={16} className="spin" />
              Iniciando proceso...
            </div>
          )}
          {log.map((linea, i) => (
            <div key={i} className="run-log-linea">
              {linea}
            </div>
          ))}
          {estado === "corriendo" && (
            <div className="run-log-linea run-log-cursor">▊</div>
          )}
        </div>

        {error && (
          <div className="run-error">
            <AlertCircle size={14} />
            <span>{error}</span>
          </div>
        )}

        <div className="modal-actions">
          {estado === "corriendo" && (
            <button className="danger" onClick={detener}>
              <Square size={14} />
              <span>Detener</span>
            </button>
          )}
          {(estado === "terminado" ||
            estado === "error" ||
            estado === "detenido") && (
            <button onClick={lanzar}>
              <Play size={14} />
              <span>Volver a ejecutar</span>
            </button>
          )}
          <button className="primary" onClick={cerrarYGuardar}>
            <Check size={14} />
            <span>Cerrar</span>
          </button>
        </div>
      </div>
    </div>
  );
}
