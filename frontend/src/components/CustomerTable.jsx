import RiskMeter from "./RiskMeter";
import RiskBadge from "./RiskBadge";
import { driverLabel } from "../risk";

export default function CustomerTable({ customers, onSelect, emptyLabel }) {
  if (!customers.length) {
    return (
      <div className="py-10 text-center text-slate-400 text-sm">
        {emptyLabel || "No customers to show."}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto w-full">
      <table className="w-full text-left text-sm text-slate-300">
        <thead className="bg-slate-900/80 text-xs uppercase font-semibold text-slate-400 border-b border-slate-700">
          <tr>
            <th className="px-6 py-4">Customer</th>
            <th className="px-6 py-4">Account Age</th>
            <th className="px-6 py-4">Daily Usage</th>
            <th className="px-6 py-4">Top Driver</th>
            <th className="px-6 py-4">Owner</th>
            <th className="px-6 py-4">Status</th>
            <th className="px-6 py-4">Risk</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-700/50 bg-slate-800/30">
          {customers.map((c) => (
            <tr
              key={c.customer_id}
              onClick={() => onSelect(c.customer_id)}
              className="hover:bg-slate-700/30 transition-colors cursor-pointer"
            >
              <td className="px-6 py-4">
                <p className="font-medium text-slate-200">{c.name}</p>
                <p className="text-xs text-slate-400">{c.email}</p>
              </td>
              <td className="px-6 py-4 font-mono text-slate-300">
                {c.account_age_days}d
              </td>
              <td className="px-6 py-4 font-mono text-slate-300">
                {c.daily_usage_mins}m
              </td>
              <td className="px-6 py-4 text-slate-300">
                {driverLabel(c.top_driver)}
              </td>
              <td className="px-6 py-4 text-slate-300 text-sm">
                {c.owner_email || <span className="text-slate-500 italic">Unassigned</span>}
              </td>
              <td className="px-6 py-4">
                <RiskBadge score={c.churn_risk_score} />
              </td>
              <td className="px-6 py-4">
                <RiskMeter score={c.churn_risk_score} width={80} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
