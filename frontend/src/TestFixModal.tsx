import { useState, useRef, useEffect } from "react";
import {
  X,
  Loader2,
  Check,
  AlertCircle,
  Wrench,
  Terminal,
  FlaskConical,
  Zap,
} from "lucide-react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface Props {
  token: string;
  nombreProyecto: string;
  onClose: () => void;
  onFinalizado: (resumen: string) => void;
}

interface Evento {
  tipo: string;
  [k: string]: any;
}

export default function TestFixModal({
  token,
  nombreProyecto,
  onClose,
  onFinalizado,
}: Props) {
  const [eventos, setEventos] = useState<Evento[]>([]);
  const [estado, setEstado] = useState<"corriendo" | "terminado" | "error">(
    "corriendo"
  );
  const [resumen, setResumen] = useState<any>(null);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [eventos]);

  useEffect(() => {
    correr();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const correr = async () => {
    try {
      const r = await fetch(
        `${API_URL}/agent/projects/${nombreProyecto}/test-fix`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      const reader = r.body?.getReader();
      if (!reader) return;
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const bloques = buffer.split("\n\n");
        buffer = bloques.pop() || "";

        for (const bloque of bloques) {
          if (!bloque.startsWith("data: ")) continue;
          const json = bloque.slice(6).trim();
          if (!json) continue;
          try {
            const ev = JSON.parse(json);
            if (ev.tipo === "cerrado") {
              setEstado("terminado");
              continue;
            }
            setEventos((prev) => [...prev, ev]);
            if (ev.tipo === "fin") {
              setResumen(ev);
              setEstado("terminado");
            }
          } catch {}
        }
      }
      setEstado("terminado");
    } catch {
      setEstado("error");
    }
  };

  const cerrarYGuardar = () => {
    const r = resumen || { exitos: 0, total: 0, correcciones: 0 };
    const texto =
      `**Test + auto-fix** sobre \`${nombreProyecto}\`\n\n` +
      `- Comandos OK: ${r.exitos} / ${r.total}\n` +
      `- Correcciones IA aplicadas: ${r.correcciones || 0}\n\n` +
      (r.exitos === r.total && r.total > 0
        ? "_Todos los tests pasaron._"
        : "_Algunos tests siguen fallando tras los reintentos. Revisa el log._");
    onFinalizado(texto);
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={cerrarYGuardar}>
      <div
        className="modal modal-wide modal-run"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-title">
          <Wrench size={20} />
          <h3>Probar + auto-fix: {nombreProyecto}</h3>
          <button className="modal-close" onClick={cerrarYGuardar}>
            <X size={16} />
          </button>
        </div>

        <div className="run-log" ref={logRef} style={{ minHeight: 300 }}>
          {eventos.length === 0 && estado === "corriendo" && (
            <div className="run-log-vacio">
              <Loader2 size={16} className="spin" />
              Detectando tests...
            </div>
          )}
          {eventos.map((ev, i) => (
            <EventoLinea key={i} ev={ev} />
          ))}
          {estado === "corriendo" && (
            <div className="run-log-linea run-log-cursor">▊</div>
          )}
        </div>

        {estado === "error" && (
          <div className="run-error">
            <AlertCircle size={14} />
            <span>Error de conexión con el backend</span>
          </div>
        )}

        <div className="modal-actions">
          <button className="primary" onClick={cerrarYGuardar}>
            <Check size={14} />
            <span>{estado === "corriendo" ? "Cerrar" : "Listo"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}

function EventoLinea({ ev }: { ev: Evento }) {
  const t = ev.tipo;
  if (t === "inicio") {
    return (
      <div className="run-log-linea" style={{ color: "#7FD4FF" }}>
        <Terminal size={12} style={{ display: "inline", marginRight: 6 }} />
        Detectados {ev.comandos?.length} comandos:
        {(ev.comandos || []).map((c: string, i: number) => (
          <div key={i} style={{ paddingLeft: 22, opacity: 0.85 }}>
            · {c}
          </div>
        ))}
      </div>
    );
  }
  if (t === "comando_inicio") {
    return (
      <div className="run-log-linea" style={{ color: "#FFD166", marginTop: 8 }}>
        ▶ [{ev.i}/{ev.total}] {ev.comando}
      </div>
    );
  }
  if (t === "intento") {
    return (
      <div className="run-log-linea" style={{ color: "#A0A0A0" }}>
        &nbsp;&nbsp;↻ Intento {ev.intento}/{ev.max}
      </div>
    );
  }
  if (t === "comando_ok") {
    return (
      <div className="run-log-linea" style={{ color: "#34C759" }}>
        <Check size={12} style={{ display: "inline", marginRight: 6 }} />
        OK ({ev.tiempo}s)
      </div>
    );
  }
  if (t === "comando_error") {
    return (
      <div className="run-log-linea" style={{ color: "#FF6B6B" }}>
        ✗ Error (intento {ev.intento}):
        <pre
          style={{
            whiteSpace: "pre-wrap",
            fontSize: "0.72rem",
            opacity: 0.85,
            margin: "4px 0 4px 20px",
          }}
        >
          {(ev.error || "").slice(0, 400)}
        </pre>
      </div>
    );
  }
  if (t === "fix_inicio") {
    return (
      <div className="run-log-linea" style={{ color: "#B18CFF", marginLeft: 10 }}>
        <Zap size={12} style={{ display: "inline", marginRight: 6 }} />
        Corrigiendo <strong>{ev.archivo}</strong> con IA...
      </div>
    );
  }
  if (t === "fix_aplicado") {
    return (
      <div className="run-log-linea" style={{ color: "#B18CFF", marginLeft: 10 }}>
        ✓ Fix aplicado en <strong>{ev.archivo}</strong> ({ev.modelo})
      </div>
    );
  }
  if (t === "fix_fallo") {
    return (
      <div className="run-log-linea" style={{ color: "#FF6B6B", marginLeft: 10 }}>
        ✗ Fix falló: {ev.error}
      </div>
    );
  }
  if (t === "fix_sin_archivo") {
    return (
      <div className="run-log-linea" style={{ color: "#FFD166", marginLeft: 10 }}>
        ⚠ No se pudo identificar el archivo: {ev.mensaje}
      </div>
    );
  }
  if (t === "fin") {
    return (
      <div
        className="run-log-linea"
        style={{ color: "#34C759", marginTop: 12, fontWeight: 600 }}
      >
        ── FIN ── {ev.exitos}/{ev.total} OK · {ev.correcciones} correcciones
      </div>
    );
  }
  if (t === "error_fatal") {
    return (
      <div className="run-log-linea" style={{ color: "#FF3B30" }}>
        <AlertCircle size={12} style={{ display: "inline", marginRight: 6 }} />
        Error fatal: {ev.mensaje}
      </div>
    );
  }
  return (
    <div className="run-log-linea" style={{ opacity: 0.5 }}>
      [{t}] {JSON.stringify(ev).slice(0, 120)}
    </div>
  );
}
