import { useState } from "react";
import {
  AlertTriangle,
  AlertCircle,
  Check,
  X,
  FileCode,
  Loader2,
  Lightbulb,
  GitBranch,
  ChevronRight,
  Undo2,
} from "lucide-react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface Props {
  token: string;
  nombreProyecto: string;
  instruccion: string;
  plan: any;
  onAplicado: (resumen: string, backupDir?: string) => void;
  onCancelar: () => void;
}

export default function EditPlan({
  token,
  nombreProyecto,
  instruccion,
  plan,
  onAplicado,
  onCancelar,
}: Props) {
  const [aplicando, setAplicando] = useState(false);
  const [error, setError] = useState("");
  const [detallesAbiertos, setDetallesAbiertos] = useState(false);
  const [alternativaSeleccionada, setAlternativaSeleccionada] = useState<number | null>(null);
  // Estado post-aplicación (permite revertir)
  const [aplicado, setAplicado] = useState(false);
  const [backupDir, setBackupDir] = useState<string | null>(null);
  const [resumenAplicado, setResumenAplicado] = useState("");
  const [revirtiendo, setRevirtiendo] = useState(false);

  const riesgoColor =
    plan.riesgo === "alto"
      ? "danger"
      : plan.riesgo === "medio"
      ? "warning"
      : "ok";

  const riesgoIcono =
    plan.riesgo === "alto" ? (
      <AlertTriangle size={14} />
    ) : plan.riesgo === "medio" ? (
      <AlertCircle size={14} />
    ) : (
      <Check size={14} />
    );

  const aplicar = async () => {
    setAplicando(true);
    setError("");

    try {
      const r = await fetch(
        `${API_URL}/agent/projects/${nombreProyecto}/edit/apply`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            instruccion,
            plan,
            autorizado: true,
          }),
        }
      );

      if (!r.ok) {
        const data = await r.json().catch(() => ({}));
        setError(data.detail || "Error al aplicar los cambios");
        setAplicando(false);
        return;
      }

      const data = await r.json();

      const aplicados = data.aplicados?.length || 0;
      const errores = data.errores?.length || 0;

      let resumen = `✅ **Cambios aplicados**\n\n`;
      resumen += `- Archivos modificados: ${aplicados}\n`;
      if (errores > 0) resumen += `- Errores: ${errores}\n`;
      resumen += `- Backup: \`${data.backup_dir}\`\n\n`;

      if (data.aplicados?.length > 0) {
        resumen += `**Archivos:**\n`;
        data.aplicados.forEach((a: any) => {
          resumen += `- \`${a.ruta}\` (${a.accion})\n`;
        });
      }

      if (data.errores?.length > 0) {
        resumen += `\n**Errores:**\n`;
        data.errores.forEach((e: any) => {
          resumen += `- \`${e.ruta}\`: ${e.error}\n`;
        });
      }

      resumen += `\n_Puedes deshacer los cambios si algo falla._`;

      // En vez de cerrar inmediatamente, mostrar panel de revertir
      setResumenAplicado(resumen);
      setBackupDir(data.backup_dir || null);
      setAplicado(true);
    } catch {
      setError("Error de conexión");
    } finally {
      setAplicando(false);
    }
  };

  const revertir = async () => {
    if (!backupDir) return;
    if (!confirm("¿Deshacer todos los cambios aplicados? Se restaurará el estado previo del proyecto.")) {
      return;
    }
    setRevirtiendo(true);
    setError("");
    try {
      const r = await fetch(
        `${API_URL}/agent/projects/${nombreProyecto}/edit/revert`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ backup_dir: backupDir }),
        }
      );
      if (!r.ok) {
        const data = await r.json().catch(() => ({}));
        setError(data.detail || "Error revirtiendo los cambios");
        setRevirtiendo(false);
        return;
      }
      const resumenRevert = "↩️ **Cambios revertidos.** Se restauró el estado previo del proyecto usando el backup.";
      onAplicado(resumenRevert, undefined);
    } catch {
      setError("Error de conexión");
    } finally {
      setRevirtiendo(false);
    }
  };

  if (aplicado) {
    return (
      <div className="edit-plan">
        <div className="edit-plan-aplicado">
          <Check size={22} />
          <div>
            <strong>Cambios aplicados correctamente</strong>
            <p>
              El backup está guardado. Si algo no funciona como esperabas,
              puedes deshacer los cambios.
            </p>
          </div>
        </div>

        <div className="edit-plan-resumen" style={{ marginTop: "0.5rem" }}>
          <pre
            style={{
              whiteSpace: "pre-wrap",
              fontFamily: "inherit",
              fontSize: "0.85rem",
              margin: 0,
              color: "var(--text-secondary, #6E6E73)",
            }}
          >
            {resumenAplicado}
          </pre>
        </div>

        {error && (
          <div className="edit-plan-error">
            <AlertCircle size={14} />
            <span>{error}</span>
          </div>
        )}

        <div className="edit-plan-acciones">
          <button
            className="btn-revertir"
            onClick={revertir}
            disabled={revirtiendo}
          >
            {revirtiendo ? (
              <Loader2 size={14} className="spin" />
            ) : (
              <Undo2 size={14} />
            )}
            <span>{revirtiendo ? "Revirtiendo..." : "Deshacer cambios"}</span>
          </button>
          <button
            className="btn-cerrar"
            onClick={() => onAplicado(resumenAplicado, backupDir || undefined)}
            disabled={revirtiendo}
          >
            <Check size={14} />
            <span>Listo</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="edit-plan">
      <div className={`edit-plan-riesgo ${riesgoColor}`}>
        {riesgoIcono}
        <span>
          <strong>Riesgo {plan.riesgo.toUpperCase()}</strong>
          {plan.razon_riesgo && ` · ${plan.razon_riesgo}`}
        </span>
      </div>

      <div className="edit-plan-resumen">
        <strong>Resumen:</strong> {plan.resumen}
      </div>

      {plan.archivos && plan.archivos.length > 0 && (
        <div className="edit-plan-seccion">
          <button
            className="edit-plan-toggle"
            onClick={() => setDetallesAbiertos(!detallesAbiertos)}
          >
            <ChevronRight
              size={13}
              className={detallesAbiertos ? "chev-rotado" : ""}
            />
            <FileCode size={13} />
            <span>
              {plan.archivos.length} archivo
              {plan.archivos.length !== 1 ? "s" : ""} a modificar
            </span>
          </button>

          {detallesAbiertos && (
            <div className="edit-plan-archivos">
              {plan.archivos.map((a: any, i: number) => (
                <div key={i} className="edit-plan-archivo">
                  <div className="edit-plan-archivo-header">
                    <code>{a.ruta}</code>
                    <span className={`edit-plan-accion ${a.accion}`}>
                      {a.accion}
                    </span>
                  </div>
                  <p>{a.descripcion}</p>
                  {a.afecta && a.afecta.length > 0 && (
                    <div className="edit-plan-afecta">
                      <strong>Afecta:</strong>
                      <ul>
                        {a.afecta.map((x: string, j: number) => (
                          <li key={j}>{x}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {plan.dependencias_afectadas && plan.dependencias_afectadas.length > 0 && (
        <div className="edit-plan-seccion warning">
          <div className="edit-plan-seccion-header">
            <GitBranch size={13} />
            <strong>Dependencias afectadas</strong>
          </div>
          <ul className="edit-plan-lista">
            {plan.dependencias_afectadas.map((d: string, i: number) => (
              <li key={i}>{d}</li>
            ))}
          </ul>
        </div>
      )}

      {plan.alternativas && plan.alternativas.length > 0 && (
        <div className="edit-plan-seccion alternativas">
          <div className="edit-plan-seccion-header">
            <Lightbulb size={13} />
            <strong>
              Alternativas para minimizar el impacto ({plan.alternativas.length})
            </strong>
          </div>
          <div className="edit-plan-alternativas">
            {plan.alternativas.map((alt: any, i: number) => (
              <div
                key={i}
                className={`edit-plan-alt-card ${
                  alternativaSeleccionada === i ? "selected" : ""
                }`}
                onClick={() =>
                  setAlternativaSeleccionada(
                    alternativaSeleccionada === i ? null : i
                  )
                }
              >
                <div className="edit-plan-alt-titulo">
                  <strong>{alt.titulo}</strong>
                  {alternativaSeleccionada === i && <Check size={12} />}
                </div>
                <p>{alt.descripcion}</p>
                {alt.trade_off && (
                  <p className="edit-plan-alt-trade">
                    <em>Trade-off:</em> {alt.trade_off}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {plan.sugerencias_extra && plan.sugerencias_extra.length > 0 && (
        <div className="edit-plan-seccion sugerencias">
          <div className="edit-plan-seccion-header">
            <Lightbulb size={13} />
            <strong>Mejoras adicionales sugeridas (opcionales)</strong>
          </div>
          <div className="edit-plan-sugerencias">
            {plan.sugerencias_extra.map((s: any, i: number) => (
              <div key={i} className="edit-plan-sug-item">
                <strong>{s.titulo}</strong>
                <p>{s.descripcion}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="edit-plan-error">
          <AlertCircle size={14} />
          <span>{error}</span>
        </div>
      )}

      <div className="edit-plan-actions">
        <button onClick={onCancelar} disabled={aplicando}>
          <X size={14} />
          <span>Cancelar</span>
        </button>
        <button
          className={`primary ${riesgoColor === "danger" ? "danger" : ""}`}
          onClick={aplicar}
          disabled={aplicando}
        >
          {aplicando ? (
            <>
              <Loader2 size={14} className="spin" />
              <span>Aplicando...</span>
            </>
          ) : (
            <>
              <Check size={14} />
              <span>
                {riesgoColor === "danger"
                  ? "Aplicar (riesgo alto)"
                  : "Aplicar cambios"}
              </span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
