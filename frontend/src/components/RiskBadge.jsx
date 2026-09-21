import { riskLevel, riskColor, riskBg, riskLabel } from "../risk";

export default function RiskBadge({ score }) {
  const level = riskLevel(score);
  return (
    <span
      style={{
        display: "inline-block",
        padding: "3px 10px",
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 600,
        color: riskColor[level],
        background: riskBg[level],
      }}
    >
      {riskLabel[level]}
    </span>
  );
}
