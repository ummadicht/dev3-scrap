import { useEffect, useState } from "react";
import { Check, Copy, Download } from "lucide-react";
import type { ScrapeRun, SourceConfigSummary } from "../types";

interface SourcesViewProps {
  sourceConfigs: SourceConfigSummary[];
  recentRuns: ScrapeRun[];
}

interface PostgresSchemaInfo {
  schema_sql: string;
  dump_path: string;
  snapshot_count: number;
  model_count: number;
}

export function SourcesView({ sourceConfigs, recentRuns }: SourcesViewProps) {
  const [pgInfo, setPgInfo] = useState<PostgresSchemaInfo | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    void (async () => {
      const resp = await fetch("/api/postgres/schema");
      if (resp.ok) {
        setPgInfo((await resp.json()) as PostgresSchemaInfo);
      }
    })();
  }, []);

  const handleCopySchema = async () => {
    if (!pgInfo?.schema_sql) return;
    await navigator.clipboard.writeText(pgInfo.schema_sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
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

      {pgInfo && (
        <section className="overflow-hidden rounded-lg border border-slate-200 bg-white">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 px-5 py-3.5">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">
                PostgreSQL 16 Schema &amp; Full Data Migration Dump
              </h2>
              <p className="text-xs text-slate-500">
                {pgInfo.snapshot_count.toLocaleString()} normalized snapshots across{" "}
                {pgInfo.model_count} models exported to{" "}
                <span className="font-mono">{pgInfo.dump_path}</span> (No authentication required)
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => void handleCopySchema()}
                className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 whitespace-nowrap shrink-0"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-emerald-700" /> : <Copy className="h-3.5 w-3.5" />}
                {copied ? "Copied DDL" : "Copy Schema DDL"}
              </button>
              <a
                href="/api/postgres/dump.sql"
                className="inline-flex items-center gap-1.5 rounded-md bg-teal-700 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-teal-800 whitespace-nowrap shrink-0"
              >
                <Download className="h-3.5 w-3.5" />
                Download Full Postgres Dump (.sql)
              </a>
            </div>
          </div>
          <div className="p-5">
            <pre className="max-h-96 overflow-y-auto rounded-md border border-slate-200 bg-slate-50 p-4 font-mono text-xs text-slate-800">
              {pgInfo.schema_sql}
            </pre>
          </div>
        </section>
      )}
    </div>
  );
}
