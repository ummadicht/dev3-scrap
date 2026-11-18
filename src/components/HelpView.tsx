import { Activity, FileText, HelpCircle, Play, Server, Zap } from "lucide-react";

export function HelpView() {
  return (
    <div className="space-y-8 pb-12">
      {/* Hero Banner */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 md:p-8 shadow-xs">
        <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-teal-50 text-teal-700">
            <HelpCircle className="h-6 w-6" />
          </div>
          <div className="space-y-1">
            <h1 className="text-xl font-bold text-slate-900">
              Swapup Scraper &amp; Price Intelligence Platform — User Guide &amp; Documentation
            </h1>
            <p className="text-sm text-slate-600">
              Comprehensive operational manual covering multi-source price collection, custom REST API integration, health monitoring, log collection, trend analytics, and Postgres migration.
            </p>
          </div>
        </div>
      </div>

      {/* Quick Navigation Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <a
          href="#managing-sources"
          className="rounded-xl border border-slate-200 bg-white p-4 transition-all hover:border-teal-400 hover:shadow-sm"
        >
          <div className="flex items-center gap-2 text-teal-700 font-semibold text-xs mb-1">
            <Server className="h-4 w-4" />
            1. Sources &amp; APIs
          </div>
          <p className="text-[11px] text-slate-500">
            Configure partner REST APIs &amp; Playwright scrapers.
          </p>
        </a>

        <a
          href="#snapshots-collection"
          className="rounded-xl border border-slate-200 bg-white p-4 transition-all hover:border-teal-400 hover:shadow-sm"
        >
          <div className="flex items-center gap-2 text-teal-700 font-semibold text-xs mb-1">
            <Play className="h-4 w-4" />
            2. Price Snapshots
          </div>
          <p className="text-[11px] text-slate-500">
            Buyback quotes, refurbished listings, and OEM parts.
          </p>
        </a>

        <a
          href="#analytics-exports"
          className="rounded-xl border border-slate-200 bg-white p-4 transition-all hover:border-teal-400 hover:shadow-sm"
        >
          <div className="flex items-center gap-2 text-teal-700 font-semibold text-xs mb-1">
            <Zap className="h-4 w-4" />
            3. Trends &amp; Exports
          </div>
          <p className="text-[11px] text-slate-500">
            DoD/WoW/MoM velocity and bucketed CSV archives.
          </p>
        </a>

        <a
          href="#health-monitor"
          className="rounded-xl border border-slate-200 bg-white p-4 transition-all hover:border-teal-400 hover:shadow-sm"
        >
          <div className="flex items-center gap-2 text-teal-700 font-semibold text-xs mb-1">
            <Activity className="h-4 w-4" />
            4. Health Monitor
          </div>
          <p className="text-[11px] text-slate-500">
            Scraper liveness, uptime checks, and API latency stats.
          </p>
        </a>

        <a
          href="#log-collector"
          className="rounded-xl border border-slate-200 bg-white p-4 transition-all hover:border-teal-400 hover:shadow-sm"
        >
          <div className="flex items-center gap-2 text-teal-700 font-semibold text-xs mb-1">
            <FileText className="h-4 w-4" />
            5. Log Collector
          </div>
          <p className="text-[11px] text-slate-500">
            Audit trails, error tracing, and scrape run history.
          </p>
        </a>
      </div>

      {/* Section 1: Managing Sources & APIs */}
      <section id="managing-sources" className="rounded-xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
        <div className="flex items-center gap-3 border-b border-slate-100 pb-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-100 text-teal-800 font-mono text-xs font-bold">
            01
          </div>
          <h2 className="text-base font-bold text-slate-900">
            Adding, Editing, and Toggling APIs &amp; Scraper Sources
          </h2>
        </div>

        <div className="space-y-3 text-sm text-slate-700 leading-relaxed">
          <p>
            The platform supports both automated Playwright web scrapers and custom partner REST APIs. All source configurations are persisted directly to YAML files under <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-800">phone-price-scraper/config/</code>.
          </p>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 pt-2">
            <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4 space-y-2">
              <h3 className="font-semibold text-slate-900 text-xs uppercase tracking-wider">
                Adding a REST API Source
              </h3>
              <ol className="list-decimal list-inside space-y-1 text-xs text-slate-600">
                <li>Navigate to the <strong className="text-slate-800">Sources &amp; Runs</strong> tab and click <strong className="text-teal-700">Add API Source</strong>.</li>
                <li>Enter a unique identifier name (e.g. <code className="font-mono bg-white px-1">partner_buyback_v2</code>).</li>
                <li>Select the target market side (<strong className="text-slate-800">Sell</strong>, <strong className="text-slate-800">Buy</strong>, <strong className="text-slate-800">New</strong>, or <strong className="text-slate-800">Parts</strong>).</li>
                <li>Provide the API endpoint URL and configure authentication (Bearer token env variable, API key header, or Basic auth).</li>
                <li>Specify the JSON response items array path (e.g., <code className="font-mono bg-white px-1">data.products</code>) and customize field mappings if needed.</li>
              </ol>
            </div>

            <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4 space-y-2">
              <h3 className="font-semibold text-slate-900 text-xs uppercase tracking-wider">
                Enabling, Disabling &amp; Testing
              </h3>
              <ul className="list-disc list-inside space-y-1 text-xs text-slate-600">
                <li><strong className="text-slate-800">Toggle Switch:</strong> Click the <strong className="text-emerald-700">Enable/Disable</strong> button on any source card to include or exclude it from collection cycles instantly.</li>
                <li><strong className="text-slate-800">On-Demand Run:</strong> Click the <strong className="text-teal-700">Run</strong> button to test collection and upsert fresh normalized records into the database.</li>
                <li><strong className="text-slate-800">Edit / Delete:</strong> Modify endpoint parameters anytime or permanently delete custom source configurations.</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Section 2: Snapshots & Collection */}
      <section id="snapshots-collection" className="rounded-xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
        <div className="flex items-center gap-3 border-b border-slate-100 pb-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-100 text-teal-800 font-mono text-xs font-bold">
            02
          </div>
          <h2 className="text-base font-bold text-slate-900">
            Price Snapshots &amp; Market Sides
          </h2>
        </div>

        <div className="space-y-3 text-sm text-slate-700 leading-relaxed">
          <p>
            The dashboard organizes price intelligence into four distinct market segments, ensuring clean separation between wholesale trade-in offers and retail prices:
          </p>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-lg border border-slate-200 bg-white p-4 space-y-1">
              <span className="font-bold text-slate-900 text-xs block">Buy · Refurbished</span>
              <p className="text-xs text-slate-500">Refurbished device prices with original MRP, discount percentages, warranty terms, and stock availability.</p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-4 space-y-1">
              <span className="font-bold text-slate-900 text-xs block">Sell · Buyback</span>
              <p className="text-xs text-slate-500">Consumer trade-in and buyback quotes categorized across condition grades (Like New, Excellent, Good, Fair, Poor).</p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-4 space-y-1">
              <span className="font-bold text-slate-900 text-xs block">New Devices</span>
              <p className="text-xs text-slate-500">Brand-new retail listings scraped exclusively from Amazon.in and Flipkart with live discount detection.</p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-4 space-y-1">
              <span className="font-bold text-slate-900 text-xs block">Parts Pricing</span>
              <p className="text-xs text-slate-500">Official OEM spare parts and repair pricing (displays, batteries, logic boards) from Samsung and Apple support.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Section 3: Analytics & Exports */}
      <section id="analytics-exports" className="rounded-xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
        <div className="flex items-center gap-3 border-b border-slate-100 pb-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-100 text-teal-800 font-mono text-xs font-bold">
            03
          </div>
          <h2 className="text-base font-bold text-slate-900">
            Trend Analytics &amp; Bucketed CSV Exports
          </h2>
        </div>

        <div className="space-y-3 text-sm text-slate-700 leading-relaxed">
          <p>
            Monitor price momentum and archive historical snapshots with built-in analytical tools:
          </p>
          <ul className="list-disc list-inside space-y-1.5 text-xs text-slate-600">
            <li><strong className="text-slate-800">DoD / WoW / MoM Trends:</strong> Automatically computes Day-over-Day, Week-over-Week, and Month-over-Month absolute and percentage price deltas, accompanied by 7-day and 30-day moving averages.</li>
            <li><strong className="text-slate-800">Bucketed CSV Archives:</strong> Export time-series snapshots and trend reports organized hierarchically by granularity (<code className="font-mono bg-slate-100 px-1">daily</code>, <code className="font-mono bg-slate-100 px-1">weekly</code>, <code className="font-mono bg-slate-100 px-1">monthly</code>) complete with SHA-256 cryptographic manifests for data integrity audits.</li>
            <li><strong className="text-slate-800">Postgres Migration Dump:</strong> Instantly copy DDL database schemas or download the full SQL migration dump for PostgreSQL 16 deployment.</li>
          </ul>
        </div>
      </section>

      {/* Section 4: Health Monitor */}
      <section id="health-monitor" className="rounded-xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
        <div className="flex items-center gap-3 border-b border-slate-100 pb-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-100 text-teal-800 font-mono text-xs font-bold">
            04
          </div>
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <Activity className="h-4 w-4 text-teal-700" /> Scraper Health Monitor &amp; Uptime Tracking
          </h2>
        </div>

        <div className="space-y-3 text-sm text-slate-700 leading-relaxed">
          <p>
            The built-in <strong className="text-slate-900">Health Monitor</strong> continuously evaluates scraper availability, database connectivity, and API responsiveness across all configured modules:
          </p>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3 pt-1">
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 space-y-1">
              <span className="font-bold text-slate-900 text-xs block">Source Status Liveness</span>
              <p className="text-xs text-slate-500">Tracks whether each source (Cashify, Amazon, Flipkart, OEM parts, custom APIs) is active, blocked, or returning HTTP errors.</p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 space-y-1">
              <span className="font-bold text-slate-900 text-xs block">Latency &amp; Rate Limits</span>
              <p className="text-xs text-slate-500">Monitors average request round-trip times and enforces exponential backoff rate limiting to prevent bot detection.</p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 space-y-1">
              <span className="font-bold text-slate-900 text-xs block">Database &amp; Storage Health</span>
              <p className="text-xs text-slate-500">Verifies row counts, Postgres foreign key integrity, and JSONB payload serialization across historical snapshot tables.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Section 5: Log Collector */}
      <section id="log-collector" className="rounded-xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
        <div className="flex items-center gap-3 border-b border-slate-100 pb-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-100 text-teal-800 font-mono text-xs font-bold">
            05
          </div>
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <FileText className="h-4 w-4 text-teal-700" /> Scrape Run Log Collector &amp; Audit Trail
          </h2>
        </div>

        <div className="space-y-3 text-sm text-slate-700 leading-relaxed">
          <p>
            Every collection execution is recorded in the immutable <strong className="text-slate-900">scrape_runs</strong> audit log table, accessible via the <strong className="text-slate-900">Sources &amp; Runs</strong> tab:
          </p>
          <ul className="list-disc list-inside space-y-1.5 text-xs text-slate-600">
            <li><strong className="text-slate-800">Idempotency &amp; Run IDs:</strong> Each scraping pass assigns a unique sequential Run ID (`#1`, `#2`, etc.) tracking start timestamps, completion timestamps, and record yields.</li>
            <li><strong className="text-slate-800">Error Capture &amp; Diagnostics:</strong> If a target host blocks requests or times out, the Log Collector records the specific error message and status code for easy debugging.</li>
            <li><strong className="text-slate-800">Raw Payload Inspection:</strong> Clicking any row in the Price Snapshots table opens the Raw Payload Inspector modal, displaying the exact JSONB data structure captured during that scrape run.</li>
          </ul>
        </div>
      </section>

      {/* Footer support note */}
      <div className="rounded-xl border border-teal-200 bg-teal-50/50 p-5 flex items-center justify-between text-xs text-teal-900">
        <span>Need assistance configuring custom webhooks or alerting? Check out the sample configurations in <code className="font-mono bg-white px-1.5 py-0.5 border border-teal-200 rounded">phone-price-scraper/config/sources/example_api.yaml</code>.</span>
        <button
          type="button"
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          className="font-semibold text-teal-700 hover:underline whitespace-nowrap ml-4"
        >
          Back to Top ↑
        </button>
      </div>
    </div>
  );
}
