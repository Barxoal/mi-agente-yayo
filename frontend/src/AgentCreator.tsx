import { useState } from "react";
import { Sparkles, X, Loader2 } from "lucide-react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface Props {
  token: string;
  onClose: () => void;
  onPlanReady: (plan: any, nombreSugerido: string) => void;
}

export default function AgentCreator({ token, onClose, onPlanReady }: Props) {
  const [brief, setBrief] = useState("");
  const [nombreSugerido, setNombreSugerido] = useState("");
  const [analizando, setAnalizando] = useState(false);
  const [error, setError] = useState("");

  const analizar = async () => {
    if (!brief.trim() || brief.length < 10) {
      setError("El brief debe tener al menos 10 caracteres");
      return;
    }
    setError("");
    setAnalizando(true);

    try {
      const r = await fetch(`${API_URL}/agent/analyze`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          brief: brief.trim(),
          nombre_sugerido: nombreSugerido.trim() || null,
        }),
      });

      if (!r.ok) {
        const data = await r.json().catch(() => ({}));
        setError(data.detail || "Error al analizar el brief");
        setAnalizando(false);
        return;
      }

      const plan = await r.json();
      onPlanReady(plan, nombreSugerido.trim() || plan.estructura.nombre_proyecto);
    } catch {
      setError("Error de conexión con el servidor");
    } finally {
      setAnalizando(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal modal-wide"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-title">
          <Sparkles size={22} />
          <h3>Crear con IA</h3>
          <button
            className="modal-close"
            onClick={onClose}
            title="Cerrar"
          >
            <X size={16} />
          </button>
        </div>

        <p className="modal-hint">
          Describe qué quieres construir. NIAH analizará tu idea, elegirá el
          mejor stack tecnológico y propondrá la estructura del proyecto.
        </p>

        <label className="modal-label">Brief del proyecto</label>
        <textarea
          className="agent-brief-input"
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          placeholder="Ej: Quiero una aplicación web para gestionar tareas con login de usuarios, categorías y fechas de vencimiento..."
          rows={6}
          autoFocus
        />

        <label className="modal-label">Nombre sugerido (opcional)</label>
        <input
          type="text"
          value={nombreSugerido}
          onChange={(e) => setNombreSugerido(e.target.value)}
          placeholder="Ej: task-manager (si lo dejas vacío, NIAH elegirá uno)"
        />

        {error && <p className="login-error">{error}</p>}

        <div className="modal-actions">
          <button onClick={onClose}>Cancelar</button>
          <button
            className="primary"
            onClick={analizar}
            disabled={analizando || brief.trim().length < 10}
          >
            {analizando ? (
              <>
                <Loader2 size={14} className="spin" />
                <span>Analizando...</span>
              </>
            ) : (
              <>
                <Sparkles size={14} />
                <span>Analizar brief</span>
              </>
            )}
          </button>
        </div>

        {analizando && (
          <p className="agent-loading-hint">
            NIAH está pensando... esto puede tardar 1-2 minutos.
          </p>
        )}
      </div>
    </div>
  );
}
