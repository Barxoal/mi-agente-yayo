import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import {
  Copy,
  Check,
  Download,
  FileText,
  FileCode,
  FileType,
  FileSpreadsheet,
  FileJson,
  File,
  ChevronDown,
  Presentation,
} from "lucide-react";
import { useState, useRef, useEffect } from "react";

interface Props {
  content: string;
  onExport?: (formato: string) => void;
}

// ===== Bloque de código =====
function CodeBlock({ language, value }: { language: string; value: string }) {
  const [copiado, setCopiado] = useState(false);

  const copiar = () => {
    navigator.clipboard.writeText(value);
    setCopiado(true);
    setTimeout(() => setCopiado(false), 1500);
  };

  return (
    <div className="code-block">
      <div className="code-header">
        <span className="code-lang">{language || "texto"}</span>
        <button className="code-copy" onClick={copiar} title="Copiar código">
          {copiado ? <Check size={13} /> : <Copy size={13} />}
          <span>{copiado ? "Copiado" : "Copiar"}</span>
        </button>
      </div>
      <SyntaxHighlighter
        language={language || "text"}
        style={oneDark}
        customStyle={{
          margin: 0,
          borderRadius: "0 0 8px 8px",
          fontSize: "0.85rem",
          background: "#0d1117",
        }}
        PreTag="div"
      >
        {value}
      </SyntaxHighlighter>
    </div>
  );
}

// ===== Barra de exportación =====
const FORMATOS_PRINCIPALES = [
  { id: "md", label: "Markdown", icono: FileCode, color: "#6366f1" },
  { id: "pdf", label: "PDF", icono: FileType, color: "#ef4444" },
  { id: "docx", label: "Word", icono: FileText, color: "#2563eb" },
  { id: "xlsx", label: "Excel", icono: FileSpreadsheet, color: "#16a34a" },
];

const FORMATOS_EXTRA = [
  { id: "pptx", label: "PowerPoint", icono: Presentation, color: "#d24726" },
  { id: "html", label: "HTML", icono: FileCode, color: "#f97316" },
  { id: "txt", label: "Texto plano", icono: File, color: "#64748b" },
  { id: "json", label: "JSON", icono: FileJson, color: "#eab308" },
];

function ExportBar({ onExport }: { onExport: (f: string) => void }) {
  const [menuAbierto, setMenuAbierto] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuAbierto(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div className="export-bar">
      <div className="export-bar-label">
        <Download size={12} />
        <span>Exportar</span>
      </div>

      <div className="export-bar-buttons">
        {FORMATOS_PRINCIPALES.map((f) => {
          const Icono = f.icono;
          return (
            <button
              key={f.id}
              className="export-chip"
              onClick={() => onExport(f.id)}
              title={`Descargar como ${f.label}`}
              style={{ "--chip-color": f.color } as React.CSSProperties}
            >
              <Icono size={13} />
              <span>{f.label}</span>
            </button>
          );
        })}

        <div className="export-menu-wrapper" ref={menuRef}>
          <button
            className={`export-chip export-chip-more ${
              menuAbierto ? "active" : ""
            }`}
            onClick={() => setMenuAbierto(!menuAbierto)}
            title="Más formatos"
          >
            <span>Más</span>
            <ChevronDown
              size={11}
              style={{
                transform: menuAbierto ? "rotate(180deg)" : "rotate(0deg)",
                transition: "transform 0.15s",
              }}
            />
          </button>

          {menuAbierto && (
            <div className="export-menu">
              {FORMATOS_EXTRA.map((f) => {
                const Icono = f.icono;
                return (
                  <button
                    key={f.id}
                    className="export-menu-item"
                    onClick={() => {
                      onExport(f.id);
                      setMenuAbierto(false);
                    }}
                  >
                    <div
                      className="export-menu-icon"
                      style={{ background: `${f.color}20`, color: f.color }}
                    >
                      <Icono size={13} />
                    </div>
                    <div className="export-menu-info">
                      <span className="export-menu-label">{f.label}</span>
                      <span className="export-menu-ext">.{f.id}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function MessageContent({ content, onExport }: Props) {
  return (
    <div className="message-content-wrapper">
      {onExport && <ExportBar onExport={onExport} />}

      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ inline, className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || "");
            const value = String(children).replace(/\n$/, "");
            if (!inline && (match || value.includes("\n"))) {
              return <CodeBlock language={match ? match[1] : ""} value={value} />;
            }
            return (
              <code className="inline-code" {...props}>
                {children}
              </code>
            );
          },
          a({ href, children }) {
            return (
              <a href={href} target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            );
          },
          table({ children }) {
            return (
              <div className="table-wrapper">
                <table className="markdown-table">{children}</table>
              </div>
            );
          },
          thead({ children }) {
            return <thead className="markdown-thead">{children}</thead>;
          },
          tbody({ children }) {
            return <tbody className="markdown-tbody">{children}</tbody>;
          },
          tr({ children }) {
            return <tr className="markdown-tr">{children}</tr>;
          },
          th({ children }) {
            return <th className="markdown-th">{children}</th>;
          },
          td({ children }) {
            return <td className="markdown-td">{children}</td>;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
