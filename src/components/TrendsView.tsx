import type { ExportGranularity, TrendRow } from "../types";

interface TrendsViewProps {
  rows: TrendRow[];
  loading: boolean;
  granularity: ExportGranularity;
  phones: string[];
  sources: string[];
  selectedPhone: string;
  selectedSource: string;
  onGranularityChange: (g: ExportGranularity) => void;
  onPhoneChange: (val: string) => void;
  onSourceChange: (val: string) => void;
}

function DeltaCell({ abs, pct }: { abs: number | null; pct: number | null }) {
  if (abs === null || pct === null) {
    return <span className="text-slate-400">—</span>;
  }
  const sign = pct > 0 ? "+" : "";
  const color = pct > 0 ? "text-emerald-700" : pct < 0 ? "text-rose-700" : "text-slate-600";
  return (
    <span className={`font-mono tabular-nums ${color}`}>
      {sign}
      {pct}% ({sign}
      {abs})
    </span>
  );
}

export function TrendsView({
  rows,
  loading,
  granularity,
  phones,
  sources,
  selectedPhone,
  selectedSource,
  onGranularityChange,
  onPhoneChange,
  onSourceChange,
}: TrendsViewProps) {
  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-end justify-between gap-4 rounded-lg border border-slate-200 bg-white p-5">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <span className="mb-1.5 block text-xs font-medium text-slate-600">Granularity</span>
            <div className="inline-flex rounded-md border border-slate-200 bg-slate-100 p-0.5">
              {(["daily", "weekly", "monthly"] as const).map((g) => (
                <button
                  key={g}
                  type="button"
                  onClick={() => onGranularityChange(g)}
                  className={`rounded px-3 py-1.5 text-xs font-medium capitalize transition-colors whitespace-nowrap shrink-0 ${
                    granularity === g
                      ? "bg-white text-slate-900 shadow-xs"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  {g}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label htmlFor="trend-phone" className="mb-1.5 block text-xs font-medium text-slate-600">
              Filter Model
            </label>
            <select
              id="trend-phone"
              value={selectedPhone}
              onChange={(e) => onPhoneChange(e.target.value)}
              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-teal-700 focus:outline-none"
            >
              <option value="all">All Models</option>
              {phones.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="trend-source" className="mb-1.5 block text-xs font-medium text-slate-600">
              Source
            </label>
            <select
              id="trend-source"
              value={selectedSource}
              onChange={(e) => onSourceChange(e.target.value)}
              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-teal-700 focus:outline-none"
            >
              <option value="all">All Sources</option>
              {sources.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
        </div>

        <p className="text-xs text-slate-500">
          {rows.length} aggregated trend buckets · DoD, WoW, MoM, 7d &amp; 30d moving averages
        </p>
      </section>

      <section className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-xs font-medium text-slate-600">
                <th className="px-4 py-2.5">Bucket</th>
                <th className="px-4 py-2.5">Model</th>
                <th className="px-4 py-2.5">Source</th>
                <th className="px-4 py-2.5">Condition</th>
                <th className="px-4 py-2.5 text-right">Avg Price</th>
                <th className="px-4 py-2.5 text-right">DoD Δ</th>
                <th className="px-4 py-2.5 text-right">WoW Δ</th>
                <th className="px-4 py-2.5 text-right">MoM Δ</th>
                <th className="px-4 py-2.5 text-right">7d MA</th>
                <th className="px-4 py-2.5 text-right">30d MA</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                Array.from({ length: 6 }).map((_, idx) => (
                  <tr key={idx}>
                    <td colSpan={10} className="px-4 py-3">
                      <div className="h-4 w-full animate-pulse rounded bg-slate-100" />
                    </td>
                  </tr>
                ))
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-4 py-10 text-center text-sm text-slate-500">
                    No trend records match the selected granularity and filters.
                  </td>
                </tr>
              ) : (
                rows.slice(0, 100).map((row, idx) => (
                  <tr
                    key={`${row.bucket_date}-${row.model}-${row.source}-${row.condition}-${idx}`}
                    className="hover:bg-slate-50"
                  >
                    <td className="px-4 py-2.5 font-mono text-xs text-slate-700 tabular-nums">
                      {row.bucket_date}
                    </td>
                    <td className="px-4 py-2.5 font-medium text-slate-900">
                      {row.brand} {row.model}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs text-slate-600">{row.source}</td>
                    <td className="px-4 py-2.5 text-xs text-slate-700">{row.condition}</td>
                    <td className="px-4 py-2.5 text-right font-mono font-medium text-slate-900 tabular-nums">
                      ₹{row.avg_price.toLocaleString("en-IN")}
                    </td>
                    <td className="px-4 py-2.5 text-right text-xs">
                      <DeltaCell abs={row.dod_abs} pct={row.dod_pct} />
                    </td>
                    <td className="px-4 py-2.5 text-right text-xs">
                      <DeltaCell abs={row.wow_abs} pct={row.wow_pct} />
                    </td>
                    <td className="px-4 py-2.5 text-right text-xs">
                      <DeltaCell abs={row.mom_abs} pct={row.mom_pct} />
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-xs text-slate-600 tabular-nums">
                      ₹{row.ma_7d.toLocaleString("en-IN")}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-xs text-slate-600 tabular-nums">
                      ₹{row.ma_30d.toLocaleString("en-IN")}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
