import { useState, useEffect } from "react";
import {
  FileText,
  FileCode,
  FileJson,
  FileSpreadsheet,
  FileType,
  File,
  ChevronRight,
  X,
  Trash2,
  Eye,
  Upload,
  Loader2,
} from "lucide-react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface Documento {
  nombre: string;
  size: number;
}

interface Props {
  token: string;
  projectId: string;
  onArchivoSeleccionado?: (nombre: string) => void;
  recargarTrigger?: number;
}

function extensionDe(nombre: string): string {
  const partes = nombre.split(".");
  return partes.length > 1 ? partes[partes.length - 1].toLowerCase() : "";
}

function iconoParaTipo(tipo: string) {
  if (["py", "js", "ts", "tsx", "jsx", "java", "go", "rs", "rb", "php", "c", "cpp", "h"].includes(tipo))
    return <FileCode size={13} />;
  if (tipo === "json") return <FileJson size={13} />;
  if (["csv", "xlsx", "xls"].includes(tipo)) return <FileSpreadsheet size={13} />;
  if (tipo === "pdf") return <FileType size={13} />;
  if (["md", "txt", "docx", "log", "yml", "yaml", "xml", "html", "css"].includes(tipo))
    return <FileText size={13} />;
  return <File size={13} />;
}
export default function UploadedFiles({
  token,
  projectId,
  onArchivoSeleccionado,
  recargarTrigger,
}: Props) {
  const [documentos, setDocumentos] = useState<Documento[]>([]);
  const [cargando, setCargando] = useState(true);
  const [abierto, setAbierto] = useState(false);
  const [docAbierto, setDocAbierto] = useState<string | null>(null);
  const [contenido, setContenido] = useState("");
  const [contenidoCargando, setContenidoCargando] = useState(false);
  const [subiendo, setSubiendo] = useState(false);

  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, recargarTrigger]);

  const cargar = async () => {
    if (!projectId) return;
    setCargando(true);
    try {
      const r = await fetch(`${API_URL}/projects/${projectId}/documents`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (r.ok) {
        const data = await r.json();
        setDocumentos(data.documentos || []);
      }
    } catch {
      /* silent */
    } finally {
      setCargando(false);
    }
  };

  const verContenido = async (nombre: string) => {
    setDocAbierto(nombre);
    setContenidoCargando(true);
    setContenido("");
    try {
      const r = await fetch(
        `${API_URL}/projects/${projectId}/documents/${encodeURIComponent(nombre)}/content`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (r.ok) {
        const data = await r.json();
        setContenido(data.contenido || "(vacío)");
        if (data.truncado) {
          setContenido((c) => c + "\n\n[... contenido truncado ...]");
        }
        onArchivoSeleccionado?.(nombre);
      } else {
        setContenido("No se pudo cargar el contenido.");
      }
    } catch {
      setContenido("Error de conexión al cargar el contenido.");
    } finally {
      setContenidoCargando(false);
    }
  };
  const eliminar = async (nombre: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`¿Eliminar "${nombre}"?`)) return;
    await fetch(
      `${API_URL}/projects/${projectId}/documents/${encodeURIComponent(nombre)}`,
      {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      }
    );
    await cargar();
  };

  const subirArchivo = async (file: File) => {
    if (!projectId) return;
    setSubiendo(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const r = await fetch(`${API_URL}/projects/${projectId}/documents`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      if (r.ok) {
        await cargar();
      } else {
        const error = await r.json().catch(() => ({}));
        alert(error.detail || "Error al subir");
      }
    } catch {
      alert("Error de conexión");
    } finally {
      setSubiendo(false);
    }
  };

  if (cargando) return null;
  if (documentos.length === 0 && !abierto) return null;

  return (
    <>
      <div className="uploaded-files">
        <button
          className="uploaded-files-header"
          onClick={() => setAbierto(!abierto)}
        >
          <ChevronRight size={13} className={abierto ? "chev-rotado" : ""} />
          <FileText size={13} />
          <span>
            {documentos.length} archivo{documentos.length !== 1 ? "s" : ""} subido
            {documentos.length !== 1 ? "s" : ""} al proyecto
          </span>
          <label
            className="uploaded-files-add"
            onClick={(e) => e.stopPropagation()}
          >
            <input
              type="file"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) subirArchivo(file);
                e.target.value = "";
              }}
              disabled={subiendo}
              style={{ display: "none" }}
            />
            {subiendo ? (
              <Loader2 size={12} className="spin" />
            ) : (
              <Upload size={12} />
            )}
            <span>{subiendo ? "Subiendo..." : "Añadir"}</span>
          </label>
        </button>

        {abierto && (
          <div className="uploaded-files-list">
            {documentos.map((d) => {
              const tipo = extensionDe(d.nombre);
              return (
                <div
                  key={d.nombre}
                  className="uploaded-file-item"
                  onClick={() => verContenido(d.nombre)}
                >
                  <div className="uploaded-file-icon">{iconoParaTipo(tipo)}</div>
                  <div className="uploaded-file-info">
                    <span className="uploaded-file-nombre">{d.nombre}</span>
                    <span className="uploaded-file-meta">
                      {tipo.toUpperCase() || "FILE"} · {(d.size / 1024).toFixed(1)} KB
                    </span>
                  </div>
                  <button
                    className="uploaded-file-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      verContenido(d.nombre);
                    }}
                    title="Ver contenido"
                  >
                    <Eye size={12} />
                  </button>
                  <button
                    className="uploaded-file-btn danger"
                    onClick={(e) => eliminar(d.nombre, e)}
                    title="Eliminar"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {docAbierto && (
        <div className="modal-overlay" onClick={() => setDocAbierto(null)}>
          <div className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
            <div className="modal-title">
              <FileText size={18} />
              <h3>{docAbierto}</h3>
              <button
                className="modal-close"
                onClick={() => setDocAbierto(null)}
              >
                <X size={16} />
              </button>
            </div>
            {contenidoCargando ? (
              <div style={{ padding: 24, textAlign: "center" }}>
                <Loader2 size={20} className="spin" />
              </div>
            ) : (
              <pre className="archivo-contenido">{contenido}</pre>
            )}
          </div>
        </div>
      )}
    </>
  );
}

