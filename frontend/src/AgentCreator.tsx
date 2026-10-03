import { useState, useRef, useEffect } from "react";
import {
  Sparkles,
  X,
  Loader2,
  Send,
  User,
  Bot,
  Check,
  Globe,
  Wand2,
  AlertCircle,
} from "lucide-react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface MensajeChat {
  role: "user" | "assistant";
  content: string;
  info_web?: string | null;
}

interface Props {
  token: string;
  onClose: () => void;
  onPlanReady: (
    plan: any,
    nombreSugerido: string,
    historial: { role: string; content: string }[]
  ) => void;
}

export default function AgentCreator({ token, onClose, onPlanReady }: Props) {
  const [briefInicial, setBriefInicial] = useState("");
  const [fase, setFase] = useState<"brief" | "chat">("brief");
  const [historial, setHistorial] = useState<MensajeChat[]>([]);
  const [input, setInput] = useState("");
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");
  const [planListo, setPlanListo] = useState<any>(null);
  const [infoWeb, setInfoWeb] = useState<string | null>(null);
  const chatRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  }, [historial, cargando, planListo]);

  const llamarRefine = async (historialActual: MensajeChat[]) => {
    setCargando(true);
    setError("");
    setInfoWeb(null);

    try {
      const r = await fetch(`${API_URL}/agent/refine`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          brief: briefInicial,
          historial: historialActual.map((m) => ({
            role: m.role,
            content: m.content,
          })),
          plan_actual: planListo,
        }),
      });

      if (!r.ok) {
        const data = await r.json().catch(() => ({}));
        setError(data.detail || "Error al refinar");
        setCargando(false);
        return;
      }

      const data = await r.json();

      if (data.info_web_usada) {
        setInfoWeb(data.info_web_usada);
      }

      let respuesta = "";
      if (data.listo) {
        respuesta = `✅ ¡Plan listo!\n\n${data.resumen || "Revisa el plan a continuación."}`;
        if (data.cambios_sugeridos) {
          respuesta += `\n\n📝 ${data.cambios_sugeridos}`;
        }
        setPlanListo(data.plan_actualizado);
      } else {
        respuesta = "Necesito saber un poco más:\n\n";
        respuesta += (data.preguntas || [])
          .map((p: string, i: number) => `${i + 1}. ${p}`)
          .join("\n");
      }

      setHistorial([
        ...historialActual,
        { role: "assistant", content: respuesta, info_web: data.info_web_usada },
      ]);
    } catch {
      setError("Error de conexión");
    } finally {
      setCargando(false);
    }
  };

  const iniciarChat = async () => {
    if (!briefInicial.trim() || briefInicial.length < 10) {
      setError("El brief debe tener al menos 10 caracteres");
      return;
    }
    setError("");
    setFase("chat");

    const primerMensaje: MensajeChat[] = [
      { role: "user", content: briefInicial.trim() },
    ];
    setHistorial(primerMensaje);
    await llamarRefine(primerMensaje);
  };

  const enviarRespuesta = async () => {
    if (!input.trim() || cargando) return;

    const nuevoHistorial: MensajeChat[] = [
      ...historial,
      { role: "user", content: input.trim() },
    ];
    setHistorial(nuevoHistorial);
    setInput("");
    await llamarRefine(nuevoHistorial);
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      enviarRespuesta();
    }
  };

  const aprobarPlan = () => {
    if (!planListo) return;
    const historialLimpio = historial.map((m) => ({
      role: m.role,
      content: m.content,
    }));
    onPlanReady(
      planListo,
      planListo.estructura.nombre_proyecto,
      historialLimpio
    );
  };

  // ===== VISTA: BRIEF INICIAL =====
  if (fase === "brief") {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
          <div className="modal-title">
            <Wand2 size={22} />
            <h3>Crear con IA</h3>
            <button className="modal-close" onClick={onClose}>
              <X size={16} />
            </button>
          </div>

          <p className="modal-hint">
            Describe qué quieres construir. NIAH te hará preguntas para
            entender mejor tu idea, y elegirá el mejor stack tecnológico.
          </p>

          <label className="modal-label">Brief del proyecto</label>
          <textarea
            className="agent-brief-input"
            value={briefInicial}
            onChange={(e) => setBriefInicial(e.target.value)}
            placeholder="Ej: Quiero una aplicación web para gestionar las citas de una clínica. Debe tener login de doctores, calendario, y ver el historial de cada paciente."
            rows={6}
            autoFocus
          />

          {error && <p className="login-error">{error}</p>}

          <div className="modal-actions">
            <button onClick={onClose}>Cancelar</button>
            <button
              className="primary"
              onClick={iniciarChat}
              disabled={briefInicial.trim().length < 10}
            >
              <Sparkles size={14} />
              <span>Comenzar conversación</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ===== VISTA: CHAT =====
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal modal-wide modal-chat"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-title">
          <Wand2 size={22} />
          <h3>Crear con IA</h3>
          <button className="modal-close" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div className="agent-chat-messages" ref={chatRef}>
          {historial.map((msg, i) => (
            <div key={i} className={`agent-msg ${msg.role}`}>
              <div className="agent-msg-icon">
                {msg.role === "user" ? <User size={14} /> : <Bot size={14} />}
              </div>
              <div className="agent-msg-body">
                {msg.info_web && (
                  <div className="agent-web-badge">
                    <Globe size={11} />
                    <span>Buscó en internet: "{msg.info_web.slice(0, 50)}..."</span>
                  </div>
                )}
                <p style={{ whiteSpace: "pre-wrap" }}>{msg.content}</p>
              </div>
            </div>
          ))}

          {cargando && (
            <div className="agent-msg assistant">
              <div className="agent-msg-icon">
                <Bot size={14} />
              </div>
              <div className="agent-msg-body">
                <div className="agent-typing">
                  <Loader2 size={14} className="spin" />
                  <span>NIAH está pensando...</span>
                </div>
              </div>
            </div>
          )}

          {planListo && (
            <div className="agent-plan-card">
              <div className="agent-plan-header">
                <Check size={16} />
                <h4>Plan propuesto</h4>
              </div>

              <div className="agent-plan-row">
                <span className="agent-plan-label">Stack</span>
                <span>
                  {[
                    planListo.stack.frontend,
                    planListo.stack.backend,
                    planListo.stack.base_datos,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              </div>

              <div className="agent-plan-row">
                <span className="agent-plan-label">Archivos</span>
                <span>{planListo.estructura.archivos.length}</span>
              </div>

              <div className="agent-plan-row">
                <span className="agent-plan-label">Tests</span>
                <span>
                  {planListo.estructura.archivos.filter((a: any) =>
                    a.ruta.toLowerCase().includes("test")
                  ).length}{" "}
                  archivos
                </span>
              </div>

              <div className="agent-plan-row">
                <span className="agent-plan-label">Tiempo</span>
                <span>~{planListo.tiempo_estimado_min} min</span>
              </div>

              {planListo.advertencias?.length > 0 && (
                <div className="agent-plan-warnings">
                  <AlertCircle size={13} />
                  <div>
                    {planListo.advertencias.map((a: string, i: number) => (
                      <p key={i}>{a}</p>
                    ))}
                  </div>
                </div>
              )}

              <details className="agent-plan-details">
                <summary>Ver archivos del proyecto</summary>
                <ul>
                  {planListo.estructura.archivos.map((a: any, i: number) => (
                    <li key={i}>
                      <code>{a.ruta}</code> — {a.descripcion}
                    </li>
                  ))}
                </ul>
              </details>
            </div>
          )}

          {error && <p className="login-error">{error}</p>}
        </div>

        {planListo ? (
          <div className="agent-actions">
            <button
              onClick={() => {
                setPlanListo(null);
                setHistorial([
                  ...historial,
                  {
                    role: "user",
                    content: "Quiero seguir refinando el plan.",
                  },
                ]);
              }}
            >
              Refinar más
            </button>
            <button className="primary" onClick={aprobarPlan}>
              <Check size={14} />
              <span>Aprobar y generar</span>
            </button>
          </div>
        ) : (
          <div className="agent-chat-input">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Escribe tu respuesta... (busca en internet si lo necesitas)"
              rows={2}
              disabled={cargando}
              autoFocus
            />
            <button
              onClick={enviarRespuesta}
              disabled={cargando || !input.trim()}
              title="Enviar"
            >
              {cargando ? (
                <Loader2 size={14} className="spin" />
              ) : (
                <Send size={14} />
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
