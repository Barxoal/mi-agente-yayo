import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Copy, Check } from "lucide-react";
import { useState } from "react";

interface Props {
  content: string;
}

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

export default function MessageContent({ content }: Props) {
  return (
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
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
