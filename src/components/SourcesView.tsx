import type { ScrapeRun, SourceConfigSummary } from "../types";

interface SourcesViewProps {
  sourceConfigs: SourceConfigSummary[];
  recentRuns: ScrapeRun[];
}

export function SourcesView({ sourceConfigs, recentRuns }: SourcesViewProps) {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
      <section className="overflow-hidden rounded-lg border border-slate-200 bg-white lg:col-span-6">
        <div className="border-b border-slate-200 px-5 py-3.5">
          <h2 className="text-sm font-semibold text-slate-900">Configured Scraper Modules</h2>
          <p className="text-xs text-slate-500">
            Loaded from phone-price-scraper/config/settings.yaml and config/sources/*.yaml
          </p>
        </div>
        <div className="divide-y divide-slate-100">
          {sourceConfigs.map((cfg) => (
            <div key={cfg.name} className="px-5 py-4">
              <div className="flex items-center justify-between gap-4">
                <span className="font-mono text-sm font-medium text-slate-900">{cfg.name}</span>
                <span className="text-xs text-slate-500">
                  {cfg.kind}
                  {cfg.auth_type ? ` · auth:${cfg.auth_type}` : ""}
                  {cfg.pagination_type ? ` · page:${cfg.pagination_type}` : ""}
                  {" · "}
                  {cfg.enabled ? "Enabled" : "Disabled"}
                </span>
              </div>
              <ul className="mt-2 space-y-1">
                {cfg.urls.map((u) => (
                  <li key={u} className="truncate font-mono text-xs text-slate-500">
                    {u}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      <section className="overflow-hidden rounded-lg border border-slate-200 bg-white lg:col-span-6">
        <div className="border-b border-slate-200 px-5 py-3.5">
          <h2 className="text-sm font-semibold text-slate-900">Recent Scrape Runs</h2>
          <p className="text-xs text-slate-500">Idempotent audit log (scrape_runs)</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-xs font-medium text-slate-600">
                <th className="px-4 py-2.5">Run ID</th>
                <th className="px-4 py-2.5">Source</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5 text-right">Records</th>
                <th className="px-4 py-2.5 text-right">Finished</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {recentRuns.map((run) => (
                <tr key={run.id} className="hover:bg-slate-50">
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-700 tabular-nums">
                    #{run.id}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-900">{run.source}</td>
                  <td className="px-4 py-2.5 text-xs font-medium text-emerald-700">{run.status}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-xs text-slate-700 tabular-nums">
                    {run.records_count}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-xs text-slate-500 tabular-nums">
                    {run.finished_at.slice(0, 19).replace("T", " ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
