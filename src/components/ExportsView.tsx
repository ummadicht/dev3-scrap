import { useState } from "react";
import { Download, FolderOutput } from "lucide-react";
import type { ExportArtifact, ExportGranularity } from "../types";

interface ExportsViewProps {
  sources: string[];
}

export function ExportsView({ sources }: ExportsViewProps) {
  const [granularity, setGranularity] = useState<ExportGranularity>("daily");
  const [source, setSource] = useState("all");
  const [fromDate, setFromDate] = useState("2026-10-01");
  const [toDate, setToDate] = useState("2026-12-31");
  const [running, setRunning] = useState(false);
  const [artifacts, setArtifacts] = useState<ExportArtifact[]>([]);
  const [error, setError] = useState<string | null>(null);

  const handleGenerateExport = async () => {
    setRunning(true);
    setError(null);
    try {
      const resp = await fetch("/api/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          granularity,
          source,
          from_date: fromDate,
          to_date: toDate,
        }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = (await resp.json()) as { artifacts: ExportArtifact[] };
      setArtifacts(data.artifacts);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <div className="mb-4">
          <h2 className="text-sm font-semibold text-slate-900">Date-Bucketed CSV &amp; Manifest Archive</h2>
          <p className="text-xs text-slate-500">
            Writes partitioned CSVs, trends reports, and SHA-256 manifest.json sidecars under{" "}
            <span className="font-mono">phone-price-scraper/exports/</span>
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-12 md:items-end">
          <div className="md:col-span-3">
            <label htmlFor="export-granularity" className="mb-1.5 block text-xs font-medium text-slate-600">
              Granularity
            </label>
            <select
              id="export-granularity"
              value={granularity}
              onChange={(e) => setGranularity(e.target.value as ExportGranularity)}
              className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-teal-700 focus:outline-none"
            >
              <option value="daily">daily (YYYY-MM-DD)</option>
              <option value="weekly">weekly (ISO YYYY-Www)</option>
              <option value="monthly">monthly (YYYY-MM)</option>
            </select>
          </div>

          <div className="md:col-span-3">
            <label htmlFor="export-source" className="mb-1.5 block text-xs font-medium text-slate-600">
              Source
            </label>
            <select
              id="export-source"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-teal-700 focus:outline-none"
            >
              <option value="all">All Sources</option>
              {sources.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-2">
            <label htmlFor="export-from" className="mb-1.5 block text-xs font-medium text-slate-600">
              From Date
            </label>
            <input
              id="export-from"
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-teal-700 focus:outline-none"
            />
          </div>

          <div className="md:col-span-2">
            <label htmlFor="export-to" className="mb-1.5 block text-xs font-medium text-slate-600">
              To Date
            </label>
            <input
              id="export-to"
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-teal-700 focus:outline-none"
            />
          </div>

          <div className="md:col-span-2 md:flex md:justify-end">
            <button
              type="button"
              onClick={handleGenerateExport}
              disabled={running}
              className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-teal-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-teal-800 disabled:opacity-50 md:w-auto whitespace-nowrap shrink-0"
            >
              <FolderOutput className="h-4 w-4" />
              {running ? "Generating..." : "Export Buckets"}
            </button>
          </div>
        </div>

        {error && <p className="mt-3 text-xs text-rose-700">{error}</p>}
      </section>

      {artifacts.length > 0 && (
        <section className="overflow-hidden rounded-lg border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-5 py-3.5">
            <h3 className="text-sm font-semibold text-slate-900">
              Generated Export Artifacts ({artifacts.length})
            </h3>
          </div>
          <div className="divide-y divide-slate-100">
            {artifacts.map((art) => (
              <div key={art.relative_path} className="p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="font-mono text-xs font-medium text-slate-900">
                      exports/{art.relative_path}
                    </div>
                    <div className="mt-1 text-xs text-slate-500">
                      {art.kind}
                      {art.row_count !== undefined ? ` · ${art.row_count} rows` : ""}
                      {art.sha256 ? ` · SHA-256 ${art.sha256.slice(0, 16)}...` : ""}
                    </div>
                  </div>
                  <a
                    href={`/api/export/download?path=${encodeURIComponent(art.relative_path)}`}
                    className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 whitespace-nowrap shrink-0"
                  >
                    <Download className="h-3.5 w-3.5" />
                    Download
                  </a>
                </div>
                {art.preview && (
                  <pre className="mt-3 overflow-x-auto rounded border border-slate-200 bg-slate-50 p-3 font-mono text-xs text-slate-700">
                    {art.preview}
                  </pre>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
