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

interface Archivo {
  nombre: string;
  bytes: number;
  tipo: string;
}

interface Props {
  token: string;
  nombreProyecto: string;
  onArchivoSeleccionado?: (nombre: string) => void;
  recargarTrigger?: number;
}

function iconoParaTipo(tipo: string) {
  if (["py", "js", "ts", "tsx", "jsx", "java", "go", "rs", "rb", "php"].includes(tipo))
    return <FileCode size={13} />;
  if (tipo === "json") return <FileJson size={13} />;
  if (["csv", "xlsx", "xls"].includes(tipo)) return <FileSpreadsheet size={13} />;
  if (tipo === "pdf") return <FileType size={13} />;
  if (["md", "txt", "docx"].includes(tipo)) return <FileText size={13} />;
  return <File size={13} />;
}

export default function UploadedFiles({
  token,
  nombreProyecto,
  onArchivoSeleccionado,
  recargarTrigger,
}: Props) {
  const [archivos, setArchivos] = useState<Archivo[]>([]);
  const [cargando, setCargando] = useState(true);
  const [abierto, setAbierto] = useState(false);
  const [archivoAbierto, setArchivoAbierto] = useState<string | null>(null);
  const [contenido, setContenido] = useState("");
  const [subiendo, setSubiendo] = useState(false);

  useEffect(() => {
    cargar();
  }, [nombreProyecto, recargarTrigger]);

  const cargar = async () => {
    setCargando(true);
    try {
      const r = await fetch(
        `${API_URL}/agent/projects/${nombreProyecto}/uploads`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (r.ok) {
        const data = await r.json();
        setArchivos(data.archivos || []);
      }
    } catch {}
    finally {
      setCargando(false);
    }
  };

  const verContenido = async (nombre: string) => {
    try {
      const r = await fetch(
        `${API_URL}/agent/projects/${nombreProyecto}/uploads/${encodeURIComponent(
          nombre
        )}/content`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (r.ok) {
        const data = await r.json();
        setContenido(data.contenido);
        setArchivoAbierto(nombre);
        onArchivoSeleccionado?.(nombre);
      }
    } catch {}
  };

  const eliminar = async (nombre: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`¿Eliminar "${nombre}"?`)) return;
    await fetch(
      `${API_URL}/agent/projects/${nombreProyecto}/uploads/${encodeURIComponent(
        nombre
      )}`,
      {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      }
    );
    await cargar();
  };

  const subirArchivo = async (file: File) => {
    setSubiendo(true);
    // Necesitamos el project_id interno. Lo obtenemos desde el nombre.
    // Pero por simplicidad, usamos el endpoint de documentos que ya acepta project_id
    // Como alternativa, llamamos al endpoint clásico con el nombre del proyecto.
    try {
      // Buscar el project_id
      const rProyectos = await fetch(`${API_URL}/projects`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const dataProyectos = await rProyectos.json();
      const proyecto = dataProyectos.proyectos.find(
        (p: any) => p.nombre === nombreProyecto
      );
      if (!proyecto) {
        alert("Proyecto no encontrado");
        setSubiendo(false);
        return;
      }

      const formData = new FormData();
      formData.append("file", file);

      const r = await fetch(
        `${API_URL}/projects/${proyecto.id}/documents`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        }
      );

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
  if (archivos.length === 0 && !abierto) return null;

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
            {archivos.length} archivo{archivos.length !== 1 ? "s" : ""} subido
            {archivos.length !== 1 ? "s" : ""} al proyecto
          </span>
          <label className="uploaded-files-add" onClick={(e) => e.stopPropagation()}>
            <input
              type="file"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) subirArchivo(file);
              }}
              disabled={subiendo}
              style={{ display: "none" }}
            />
            {subiendo ? <Loader2 size={12} className="spin" /> : <Upload size={12} />}
            <span>{subiendo ? "Subiendo..." : "Añadir"}</span>
          </label>
        </button>

        {abierto && (
          <div className="uploaded-files-list">
            {archivos.map((a) => (
              <div
                key={a.nombre}
                className="uploaded-file-item"
                onClick={() => verContenido(a.nombre)}
              >
                <div className="uploaded-file-icon">
                  {iconoParaTipo(a.tipo)}
                </div>
                <div className="uploaded-file-info">
                  <span className="uploaded-file-nombre">{a.nombre}</span>
                  <span className="uploaded-file-meta">
                    {a.tipo.toUpperCase()} · {(a.bytes / 1024).toFixed(1)} KB
                  </span>
                </div>
                <button
                  className="uploaded-file-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    verContenido(a.nombre);
                  }}
                  title="Ver contenido"
                >
                  <Eye size={12} />
                </button>
                <button
                  className="uploaded-file-btn danger"
                  onClick={(e) => eliminar(a.nombre, e)}
                  title="Eliminar"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {archivoAbierto && (
        <div className="modal-overlay" onClick={() => setArchivoAbierto(null)}>
          <div className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
            <div className="modal-title">
              <FileText size={18} />
              <h3>{archivoAbierto}</h3>
              <button
                className="modal-close"
                onClick={() => setArchivoAbierto(null)}
              >
                <X size={16} />
              </button>
            </div>
            <pre className="archivo-contenido">{contenido}</pre>
          </div>
        </div>
      )}
    </>
  );
}
