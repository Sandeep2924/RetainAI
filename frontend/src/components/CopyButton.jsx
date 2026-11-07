import { useState } from "react";
import { Copy, Check } from "lucide-react";

export default function CopyButton({
  text,
  label = "",
  copiedLabel = "Copied!",
  title = "Copy to clipboard",
  style = {},
  className = "",
  size = 14,
}) {
  const [copied, setCopied] = useState(false);

  async function handleCopy(e) {
    e.stopPropagation();
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers / iframe contexts
      const el = document.createElement("textarea");
      el.value = text;
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      title={copied ? "Copied to clipboard!" : title}
      className={className}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: label ? "5px 10px" : "5px 7px",
        borderRadius: "6px",
        fontSize: "12px",
        fontWeight: 500,
        color: copied ? "#34d399" : "var(--text-secondary, #94a3b8)",
        background: copied ? "rgba(16, 185, 129, 0.12)" : "rgba(51, 65, 85, 0.35)",
        border: `1px solid ${copied ? "rgba(16, 185, 129, 0.35)" : "var(--border, rgba(51, 65, 85, 0.6))"}`,
        cursor: "pointer",
        transition: "all 0.15s ease",
        ...style,
      }}
    >
      {copied ? (
        <Check style={{ width: size, height: size, color: "#34d399" }} />
      ) : (
        <Copy style={{ width: size, height: size }} />
      )}
      {(label || copied) && (
        <span>{copied ? copiedLabel : label}</span>
      )}
    </button>
  );
}
