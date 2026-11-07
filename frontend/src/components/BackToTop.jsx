import { useState, useEffect } from "react";
import { ArrowUp } from "lucide-react";

export default function BackToTop({ targetId = "main-content" }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const target = document.getElementById(targetId) || window;

    function handleScroll() {
      const scrollTop = target === window ? window.scrollY : target.scrollTop;
      if (scrollTop > 240) {
        setVisible(true);
      } else {
        setVisible(false);
      }
    }

    target.addEventListener("scroll", handleScroll, { passive: true });
    return () => target.removeEventListener("scroll", handleScroll);
  }, [targetId]);

  function scrollToTop() {
    const target = document.getElementById(targetId);
    if (target) {
      target.scrollTo({ top: 0, behavior: "smooth" });
    } else {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }

  if (!visible) return null;

  return (
    <button
      type="button"
      onClick={scrollToTop}
      title="Back to top"
      aria-label="Back to top"
      style={{
        position: "fixed",
        bottom: "24px",
        right: "84px", // Positioned to the left of the floating support widget
        zIndex: 40,
        width: "42px",
        height: "42px",
        borderRadius: "50%",
        backgroundColor: "#1e293b",
        border: "1px solid rgba(6, 182, 212, 0.4)",
        color: "#38bdf8",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        cursor: "pointer",
        boxShadow: "0 8px 20px rgba(0, 0, 0, 0.45)",
        transition: "all 0.2s cubic-bezier(0.16, 1, 0.3, 1)",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.backgroundColor = "#0f172a";
        e.currentTarget.style.borderColor = "#38bdf8";
        e.currentTarget.style.transform = "translateY(-3px)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.backgroundColor = "#1e293b";
        e.currentTarget.style.borderColor = "rgba(6, 182, 212, 0.4)";
        e.currentTarget.style.transform = "translateY(0)";
      }}
    >
      <ArrowUp style={{ width: 18, height: 18 }} />
    </button>
  );
}
