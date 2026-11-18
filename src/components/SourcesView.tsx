import { useEffect, useState } from "react";
import {
  Check,
  Copy,
  Download,
  Edit3,
  Globe,
  Play,
  Plus,
  Power,
  Server,
  Trash2,
  X,
} from "lucide-react";
import type { MarketSide, ScrapeRun, SourceConfigSummary } from "../types";

interface SourcesViewProps {
  sourceConfigs: SourceConfigSummary[];
  recentRuns: ScrapeRun[];
  onSourcesChanged?: () => Promise<void> | void;
}

interface PostgresSchemaInfo {
  schema_sql: string;
  dump_path: string;
  snapshot_count: number;
  model_count: number;
}

type FilterMode = "all" | "generic_api" | "playwright" | "enabled" | "disabled";

const DEFAULT_FIELD_MAP: Record<string, string> = {
  source_product_id: "sku_id",
  brand: "device.brand",
  model: "device.model_name",
  storage_gb: "specs.storage",
  ram_gb: "specs.ram",
  color: "specs.color",
  condition: "grade",
  price: "pricing.offer_price",
  currency: "pricing.currency",
  mrp: "pricing.retail_mrp",
  in_stock: "availability.in_stock",
  source_url: "listing_url",
};

const FIELD_MAP_LABELS: Array<{ key: string; label: string; placeholder: string }> = [
  { key: "source_product_id", label: "Product / SKU ID Path", placeholder: "sku_id" },
  { key: "brand", label: "Brand Path", placeholder: "device.brand" },
  { key: "model", label: "Model Name Path", placeholder: "device.model_name" },
  { key: "price", label: "Offer / Selling Price Path", placeholder: "pricing.offer_price" },
  { key: "mrp", label: "Retail MRP Path", placeholder: "pricing.retail_mrp" },
  { key: "condition", label: "Condition / Grade Path", placeholder: "grade" },
  { key: "storage_gb", label: "Storage Path", placeholder: "specs.storage" },
  { key: "ram_gb", label: "RAM Path", placeholder: "specs.ram" },
  { key: "color", label: "Color Path", placeholder: "specs.color" },
  { key: "currency", label: "Currency Path", placeholder: "pricing.currency" },
  { key: "in_stock", label: "In-Stock Boolean Path", placeholder: "availability.in_stock" },
  { key: "source_url", label: "Listing URL Path", placeholder: "listing_url" },
];

interface SourceFormState {
  raw_name: string;
  kind: "generic_api" | "playwright";
  side: MarketSide;
  enabled: boolean;
  apiUrl: string;
  playwrightUrlsText: string;
  method: "GET" | "POST";
  auth_type: string;
  auth_token_env: string;
  auth_header_name: string;
  pagination_type: string;
  pagination_param: string;
  pagination_path: string;
  max_pages: number;
  items_path: string;
  paramsText: string;
  headersText: string;
  field_map: Record<string, string>;
  timeout_sec: number;
}

function recordToKeyValueLines(rec?: Record<string, string>): string {
  if (!rec || Object.keys(rec).length === 0) return "";
  return Object.entries(rec)
    .map(([k, v]) => `${k}=${v}`)
    .join("\n");
}

function parseKeyValueLines(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const rawLine of text.split("\n")) {
    const line = rawLine.trim();
    if (!line) continue;
    const eqIdx = line.indexOf("=");
    const colonIdx = line.indexOf(":");
    const sepIdx =
      eqIdx >= 0 && (colonIdx < 0 || eqIdx < colonIdx) ? eqIdx : colonIdx;
    if (sepIdx > 0) {
      const k = line.slice(0, sepIdx).trim();
      const v = line.slice(sepIdx + 1).trim();
      if (k) out[k] = v;
    }
  }
  return out;
}

function createInitialFormState(cfg?: SourceConfigSummary | null): SourceFormState {
  if (!cfg) {
    return {
      raw_name: "",
      kind: "generic_api",
      side: "sell",
      enabled: true,
      apiUrl: "https://api.partner-marketplace.example.com/v1/phones/buyback-quotes",
      playwrightUrlsText: "https://www.cashify.in/sell-old-mobile-phone/used-apple-iphone-15",
      method: "GET",
      auth_type: "bearer",
      auth_token_env: "PARTNER_API_KEY",
      auth_header_name: "Authorization",
      pagination_type: "cursor",
      pagination_param: "cursor",
      pagination_path: "pagination.next_cursor",
      max_pages: 20,
      items_path: "data.products",
      paramsText: "country=IN\ncategory=smartphones",
      headersText: "Accept=application/json",
      field_map: { ...DEFAULT_FIELD_MAP },
      timeout_sec: 15,
    };
  }

  const rawName = cfg.raw_name ?? cfg.name.replace(/^api:/, "");
  return {
    raw_name: rawName,
    kind: cfg.kind,
    side: cfg.side ?? "sell",
    enabled: cfg.enabled,
    apiUrl: cfg.urls[0] ?? "",
    playwrightUrlsText: cfg.urls.join("\n"),
    method: cfg.method ?? "GET",
    auth_type: cfg.auth_type ?? "none",
    auth_token_env: cfg.auth_token_env ?? "",
    auth_header_name: cfg.auth_header_name ?? "",
    pagination_type: cfg.pagination_type ?? "none",
    pagination_param: cfg.pagination_param ?? "cursor",
    pagination_path: cfg.pagination_path ?? "pagination.next_cursor",
    max_pages: cfg.max_pages ?? 20,
    items_path: cfg.items_path ?? "data.products",
    paramsText:
      recordToKeyValueLines(cfg.params) || "country=IN\ncategory=smartphones",
    headersText:
      recordToKeyValueLines(cfg.headers) || "Accept=application/json",
    field_map: { ...DEFAULT_FIELD_MAP, ...(cfg.field_map ?? {}) },
    timeout_sec: cfg.timeout_sec ?? (cfg.kind === "generic_api" ? 15 : 20),
  };
}

export function SourcesView({
  sourceConfigs,
  recentRuns,
  onSourcesChanged,
}: SourcesViewProps) {
  const [pgInfo, setPgInfo] = useState<PostgresSchemaInfo | null>(null);
  const [copied, setCopied] = useState(false);

  const [filterMode, setFilterMode] = useState<FilterMode>("all");
  const [formOpen, setFormOpen] = useState(false);
  const [editingOriginalName, setEditingOriginalName] = useState<string | null>(null);
  const [formState, setFormState] = useState<SourceFormState>(() =>
    createInitialFormState(null),
  );
  const [showAdvancedMapping, setShowAdvancedMapping] = useState(false);

  const [saving, setSaving] = useState(false);
  const [togglingName, setTogglingName] = useState<string | null>(null);
  const [runningSource, setRunningSource] = useState<string | null>(null);
  const [confirmDeleteName, setConfirmDeleteName] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

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

  const openAddForm = (defaultKind: "generic_api" | "playwright" = "generic_api") => {
    const initial = createInitialFormState(null);
    initial.kind = defaultKind;
    setEditingOriginalName(null);
    setFormState(initial);
    setShowAdvancedMapping(false);
    setFormOpen(true);
    setFeedback(null);
  };

  const openEditForm = (cfg: SourceConfigSummary) => {
    setEditingOriginalName(cfg.name);
    setFormState(createInitialFormState(cfg));
    setShowAdvancedMapping(false);
    setFormOpen(true);
    setFeedback(null);
  };

  const closeForm = () => {
    setFormOpen(false);
    setEditingOriginalName(null);
  };

  const handleToggleEnabled = async (cfg: SourceConfigSummary) => {
    setTogglingName(cfg.name);
    setFeedback(null);
    try {
      const resp = await fetch(
        `/api/sources/${encodeURIComponent(cfg.name)}/toggle`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: !cfg.enabled }),
        },
      );
      const data = (await resp.json()) as { error?: string; source?: SourceConfigSummary };
      if (!resp.ok) {
        throw new Error(data.error ?? "Failed to update source state");
      }
      setFeedback({
        type: "success",
        message: `Source '${cfg.name}' is now ${!cfg.enabled ? "enabled" : "disabled"}.`,
      });
      await onSourcesChanged?.();
    } catch (err) {
      setFeedback({
        type: "error",
        message: err instanceof Error ? err.message : "Failed to toggle source",
      });
    } finally {
      setTogglingName(null);
    }
  };

  const handleDeleteSource = async (cfg: SourceConfigSummary) => {
    setFeedback(null);
    try {
      const resp = await fetch(`/api/sources/${encodeURIComponent(cfg.name)}`, {
        method: "DELETE",
      });
      const data = (await resp.json()) as { error?: string };
      if (!resp.ok) {
        throw new Error(data.error ?? "Failed to delete source");
      }
      setConfirmDeleteName(null);
      if (editingOriginalName === cfg.name) {
        closeForm();
      }
      setFeedback({
        type: "success",
        message: `Deleted source '${cfg.name}'.`,
      });
      await onSourcesChanged?.();
    } catch (err) {
      setFeedback({
        type: "error",
        message: err instanceof Error ? err.message : "Failed to delete source",
      });
    }
  };

  const handleRunSourceScrape = async (cfg: SourceConfigSummary) => {
    const rawName = cfg.raw_name ?? cfg.name.replace(/^api:/, "");
    setRunningSource(cfg.name);
    setFeedback(null);
    try {
      const resp = await fetch("/api/scrape", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          side: cfg.side ?? "sell",
          source: rawName,
          phone: "all",
        }),
      });
      const data = (await resp.json()) as {
        error?: string;
        collected_count?: number;
        run?: { id: number };
      };
      if (!resp.ok) {
        throw new Error(data.error ?? `Scrape failed (${resp.status})`);
      }
      setFeedback({
        type: "success",
        message: `Run #${data.run?.id ?? "—"} finished for '${cfg.name}': ${data.collected_count ?? 0} normalized records collected.`,
      });
      await onSourcesChanged?.();
    } catch (err) {
      setFeedback({
        type: "error",
        message: err instanceof Error ? err.message : "Failed to run source scrape",
      });
    } finally {
      setRunningSource(null);
    }
  };

  const handleSubmitForm = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanRawName = formState.raw_name
      .replace(/^api:/, "")
      .trim()
      .replace(/[^a-zA-Z0-9_.-]/g, "_");
    if (!cleanRawName) {
      setFeedback({ type: "error", message: "Please provide a valid source identifier." });
      return;
    }

    const urls =
      formState.kind === "generic_api"
        ? [formState.apiUrl.trim()].filter(Boolean)
        : formState.playwrightUrlsText
            .split("\n")
            .map((u) => u.trim())
            .filter(Boolean);

    if (urls.length === 0) {
      setFeedback({
        type: "error",
        message:
          formState.kind === "generic_api"
            ? "Please provide an API endpoint URL."
            : "Please provide at least one target URL.",
      });
      return;
    }

    setSaving(true);
    setFeedback(null);
    try {
      const payload: Partial<SourceConfigSummary> = {
        raw_name: cleanRawName,
        name: formState.kind === "generic_api" ? `api:${cleanRawName}` : cleanRawName,
        kind: formState.kind,
        side: formState.side,
        enabled: formState.enabled,
        urls,
        method: formState.method,
        auth_type: formState.auth_type,
        auth_token_env: formState.auth_token_env.trim(),
        auth_header_name: formState.auth_header_name.trim(),
        pagination_type: formState.pagination_type,
        pagination_param: formState.pagination_param.trim() || "cursor",
        pagination_path: formState.pagination_path.trim() || "pagination.next_cursor",
        max_pages: Number(formState.max_pages) || 20,
        items_path: formState.items_path.trim() || "data.products",
        params: parseKeyValueLines(formState.paramsText),
        headers: parseKeyValueLines(formState.headersText),
        field_map: formState.field_map,
        timeout_sec: Number(formState.timeout_sec) || 15,
      };

      const isEditing = Boolean(editingOriginalName);
      const endpoint = isEditing
        ? `/api/sources/${encodeURIComponent(editingOriginalName!)}`
        : "/api/sources";

      const resp = await fetch(endpoint, {
        method: isEditing ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = (await resp.json()) as { error?: string; source?: SourceConfigSummary };
      if (!resp.ok) {
        throw new Error(data.error ?? "Failed to save source configuration");
      }

      setFeedback({
        type: "success",
        message: isEditing
          ? `Updated source '${data.source?.name ?? cleanRawName}'.`
          : `Added new ${formState.kind === "generic_api" ? "API" : "scraper"} source '${data.source?.name ?? cleanRawName}'.`,
      });
      closeForm();
      await onSourcesChanged?.();
    } catch (err) {
      setFeedback({
        type: "error",
        message: err instanceof Error ? err.message : "Failed to save source",
      });
    } finally {
      setSaving(false);
    }
  };

  const filteredSources = sourceConfigs.filter((cfg) => {
    if (filterMode === "generic_api") return cfg.kind === "generic_api";
    if (filterMode === "playwright") return cfg.kind === "playwright";
    if (filterMode === "enabled") return cfg.enabled;
    if (filterMode === "disabled") return !cfg.enabled;
    return true;
  });

  const apiCount = sourceConfigs.filter((c) => c.kind === "generic_api").length;
  const scraperCount = sourceConfigs.filter((c) => c.kind === "playwright").length;
  const enabledCount = sourceConfigs.filter((c) => c.enabled).length;
  const disabledCount = sourceConfigs.length - enabledCount;

  return (
    <div className="space-y-6">
      {/* Top Action & Filter Bar */}
      <section className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-slate-200 bg-white px-5 py-4">
        <div className="space-y-1">
          <h2 className="text-sm font-semibold text-slate-900">
            API &amp; Scraper Source Management
          </h2>
          <p className="text-xs text-slate-500">
            Add partner REST APIs or Playwright scrapers, edit endpoints &amp; field mappings, and enable or disable collection modules.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => openAddForm("generic_api")}
            className="inline-flex items-center gap-1.5 rounded-md bg-teal-700 px-3.5 py-2 text-xs font-medium text-white transition-colors hover:bg-teal-800 whitespace-nowrap shrink-0"
          >
            <Plus className="h-3.5 w-3.5" />
            Add API Source
          </button>
          <button
            type="button"
            onClick={() => openAddForm("playwright")}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3.5 py-2 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 whitespace-nowrap shrink-0"
          >
            <Plus className="h-3.5 w-3.5" />
            Add Web Scraper
          </button>
        </div>
      </section>

      {feedback && (
        <div
          className={`flex items-center justify-between rounded-lg border px-4 py-3 text-xs font-medium ${
            feedback.type === "success"
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-rose-200 bg-rose-50 text-rose-800"
          }`}
        >
          <span>{feedback.message}</span>
          <button
            type="button"
            onClick={() => setFeedback(null)}
            className="ml-4 rounded p-0.5 hover:bg-black/5"
            aria-label="Dismiss message"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Add / Edit Source Form Panel */}
      {formOpen && (
        <section className="overflow-hidden rounded-lg border border-teal-700/30 bg-white shadow-xs">
          <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-5 py-3.5">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                {editingOriginalName
                  ? `Edit Source: ${editingOriginalName}`
                  : formState.kind === "generic_api"
                    ? "Add New REST API Source"
                    : "Add New Web Scraper Source"}
              </h3>
              <p className="text-xs text-slate-500">
                {formState.kind === "generic_api"
                  ? "Persists to phone-price-scraper/config/sources/<name>.yaml"
                  : "Persists to phone-price-scraper/config/settings.yaml"}
              </p>
            </div>
            <button
              type="button"
              onClick={closeForm}
              className="rounded-md p-1.5 text-slate-500 hover:bg-slate-200/60 hover:text-slate-900"
              aria-label="Close form"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <form onSubmit={(e) => void handleSubmitForm(e)} className="space-y-5 p-5">
            {/* Row 1: Kind, Name, Market Side, Enabled Toggle */}
            <div className="grid grid-cols-1 gap-4 md:grid-cols-12">
              <div className="md:col-span-3">
                <label className="mb-1.5 block text-xs font-medium text-slate-700">
                  Source Type
                </label>
                <div className="grid grid-cols-2 gap-1 rounded-md border border-slate-300 bg-slate-100 p-0.5">
                  <button
                    type="button"
                    onClick={() => setFormState((s) => ({ ...s, kind: "generic_api" }))}
                    className={`inline-flex items-center justify-center gap-1.5 rounded py-1.5 text-xs font-medium transition-colors ${
                      formState.kind === "generic_api"
                        ? "bg-white text-slate-900 shadow-2xs"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    <Server className="h-3.5 w-3.5" />
                    REST API
                  </button>
                  <button
                    type="button"
                    onClick={() => setFormState((s) => ({ ...s, kind: "playwright" }))}
                    className={`inline-flex items-center justify-center gap-1.5 rounded py-1.5 text-xs font-medium transition-colors ${
                      formState.kind === "playwright"
                        ? "bg-white text-slate-900 shadow-2xs"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    <Globe className="h-3.5 w-3.5" />
                    Scraper
                  </button>
                </div>
              </div>

              <div className="md:col-span-4">
                <label
                  htmlFor="source-raw-name"
                  className="mb-1.5 block text-xs font-medium text-slate-700"
                >
                  Source Identifier
                </label>
                <div className="flex items-center">
                  {formState.kind === "generic_api" && (
                    <span className="inline-flex items-center rounded-l-md border border-r-0 border-slate-300 bg-slate-100 px-2.5 py-2 font-mono text-xs text-slate-600">
                      api:
                    </span>
                  )}
                  <input
                    id="source-raw-name"
                    type="text"
                    required
                    value={formState.raw_name}
                    onChange={(e) =>
                      setFormState((s) => ({ ...s, raw_name: e.target.value }))
                    }
                    placeholder={
                      formState.kind === "generic_api"
                        ? "partner_quotes_api"
                        : "cashify_sell"
                    }
                    className={`w-full border border-slate-300 bg-white px-3 py-2 font-mono text-xs text-slate-900 focus:border-teal-700 focus:outline-none ${
                      formState.kind === "generic_api" ? "rounded-r-md" : "rounded-md"
                    }`}
                  />
                </div>
              </div>

              <div className="md:col-span-3">
                <label
                  htmlFor="source-side"
                  className="mb-1.5 block text-xs font-medium text-slate-700"
                >
                  Market Side
                </label>
                <select
                  id="source-side"
                  value={formState.side}
                  onChange={(e) =>
                    setFormState((s) => ({
                      ...s,
                      side: e.target.value as MarketSide,
                    }))
                  }
                  className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 focus:border-teal-700 focus:outline-none"
                >
                  <option value="sell">Sell · Buyback Quotes</option>
                  <option value="buy">Buy · Refurbished Retail</option>
                  <option value="new">New Devices · Retail</option>
                  <option value="parts">Parts Pricing · OEM</option>
                </select>
              </div>

              <div className="flex flex-col justify-end md:col-span-2">
                <label className="mb-1.5 block text-xs font-medium text-slate-700">
                  Status
                </label>
                <button
                  type="button"
                  role="switch"
                  aria-checked={formState.enabled}
                  onClick={() =>
                    setFormState((s) => ({ ...s, enabled: !s.enabled }))
                  }
                  className={`inline-flex items-center justify-between rounded-md border px-3 py-2 text-xs font-medium transition-colors ${
                    formState.enabled
                      ? "border-emerald-300 bg-emerald-50 text-emerald-800"
                      : "border-slate-300 bg-slate-100 text-slate-600"
                  }`}
                >
                  <span>{formState.enabled ? "Enabled" : "Disabled"}</span>
                  <span
                    className={`h-2.5 w-2.5 rounded-full ${
                      formState.enabled ? "bg-emerald-600" : "bg-slate-400"
                    }`}
                  />
                </button>
              </div>
            </div>

            {formState.kind === "generic_api" ? (
              <>
                {/* REST API Endpoint, Method, Timeout, Items Path */}
                <div className="grid grid-cols-1 gap-4 md:grid-cols-12">
                  <div className="md:col-span-2">
                    <label
                      htmlFor="api-method"
                      className="mb-1.5 block text-xs font-medium text-slate-700"
                    >
                      HTTP Method
                    </label>
                    <select
                      id="api-method"
                      value={formState.method}
                      onChange={(e) =>
                        setFormState((s) => ({
                          ...s,
                          method: e.target.value as "GET" | "POST",
                        }))
                      }
                      className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 font-mono text-xs text-slate-900 focus:border-teal-700 focus:outline-none"
                    >
                      <option value="GET">GET</option>
                      <option value="POST">POST</option>
                    </select>
                  </div>

                  <div className="md:col-span-6">
                    <label
                      htmlFor="api-endpoint-url"
                      className="mb-1.5 block text-xs font-medium text-slate-700"
                    >
                      API Endpoint URL
                    </label>
                    <input
                      id="api-endpoint-url"
                      type="url"
                      required
                      value={formState.apiUrl}
                      onChange={(e) =>
                        setFormState((s) => ({ ...s, apiUrl: e.target.value }))
                      }
                      placeholder="https://api.partner.example.com/v1/phones/quotes"
                      className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 font-mono text-xs text-slate-900 focus:border-teal-700 focus:outline-none"
                    />
                  </div>

                  <div className="md:col-span-2">
                    <label
                      htmlFor="api-items-path"
                      className="mb-1.5 block text-xs font-medium text-slate-700"
                    >
                      Items JSON Path
                    </label>
                    <input
                      id="api-items-path"
                      type="text"
                      value={formState.items_path}
                      onChange={(e) =>
                        setFormState((s) => ({
                          ...s,
                          items_path: e.target.value,
                        }))
                      }
                      placeholder="data.products"
                      className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 font-mono text-xs text-slate-900 focus:border-teal-700 focus:outline-none"
                    />
                  </div>

                  <div className="md:col-span-2">
                    <label
                      htmlFor="api-timeout"
                      className="mb-1.5 block text-xs font-medium text-slate-700"
                    >
                      Timeout (sec)
                    </label>
                    <input
                      id="api-timeout"
                      type="number"
                      min={1}
                      max={120}
                      value={formState.timeout_sec}
                      onChange={(e) =>
                        setFormState((s) => ({
                          ...s,
                          timeout_sec: Number(e.target.value),
                        }))
                      }
                      className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 font-mono text-xs text-slate-900 focus:border-teal-700 focus:outline-none"
                    />
                  </div>
                </div>

                {/* Auth & Pagination Settings */}
                <div className="grid grid-cols-1 gap-4 rounded-md border border-slate-200 bg-slate-50/70 p-4 md:grid-cols-12">
                  <div className="md:col-span-3">
                    <label
                      htmlFor="api-auth-type"
                      className="mb-1.5 block text-xs font-medium text-slate-700"
                    >
                      Authentication Type
                    </label>
                    <select
                      id="api-auth-type"
                      value={formState.auth_type}
                      onChange={(e) =>
                        setFormState((s) => ({
                          ...s,
                          auth_type: e.target.value,
                        }))
                      }
                      className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 focus:border-teal-700 focus:outline-none"
                    >
                      <option value="none">None (Public Endpoint)</option>
                      <option value="bearer">Bearer Token (Env Var)</option>
                      <option value="api_key">API Key Header (Env Var)</option>
                      <option value="basic">HTTP Basic Auth</option>
                      <option value="oauth2">OAuth2 Client Credentials</option>
                    </select>
                  </div>

                  <div className="md:col-span-3">
                    <label
                      htmlFor="api-token-env"
                      className="mb-1.5 block text-xs font-medium text-slate-700"
                    >
                      Token Env Variable
                    </label>
                    <input
                      id="api-token-env"
                      type="text"
                      disabled={formState.auth_type === "none"}
                      value={formState.auth_token_env}
                      onChange={(e) =>
                        setFormState((s) => ({
                          ...s,
                          auth_token_env: e.target.value,
                        }))
                      }
                      placeholder="EXAMPLE_API_BEARER_TOKEN"
                      className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 font-mono text-xs text-slate-900 disabled:bg-slate-100 disabled:text-slate-400 focus:border-teal-700 focus:outline-none"
                    />
                  </div>

                  <div className="md:col-span-2">
                    <label
                      htmlFor="api-pagination-type"
                      className="mb-1.5 block text-xs font-medium text-slate-700"
                    >
                      Pagination
                    </label>
                    <select
                      id="api-pagination-type"
                      value={formState.pagination_type}
                      onChange={(e) =>
                        setFormState((s) => ({
                          ...s,
                          pagination_type: e.target.value,
                        }))
                      }
                      className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 focus:border-teal-700 focus:outline-none"
                    >
                      <option value="none">None (Single Page)</option>
                      <option value="cursor">Cursor Token</option>
                      <option value="page">Page Number</option>
                      <option value="offset">Limit / Offset</option>
                    </select>
                  </div>

                  <div className="md:col-span-2">
                    <label
                      htmlFor="api-pagination-param"
                      className="mb-1.5 block text-xs font-medium text-slate-700"
                    >
                      Cursor / Page Param
                    </label>
                    <input
                      id="api-pagination-param"
                      type="text"
                      disabled={formState.pagination_type === "none"}
                      value={formState.pagination_param}
                      onChange={(e) =>
                        setFormState((s) => ({
                          ...s,
                          pagination_param: e.target.value,
                        }))
                      }
                      placeholder="cursor"
                      className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 font-mono text-xs text-slate-900 disabled:bg-slate-100 disabled:text-slate-400 focus:border-teal-700 focus:outline-none"
                    />
                  </div>

                  <div className="md:col-span-2">
                    <label
                      htmlFor="api-pagination-path"
                      className="mb-1.5 block text-xs font-medium text-slate-700"
                    >
                      Next Cursor Path
                    </label>
                    <input
                      id="api-pagination-path"
                      type="text"
                      disabled={formState.pagination_type === "none"}
                      value={formState.pagination_path}
                      onChange={(e) =>
                        setFormState((s) => ({
                          ...s,
                          pagination_path: e.target.value,
                        }))
                      }
                      placeholder="pagination.next_cursor"
                      className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 font-mono text-xs text-slate-900 disabled:bg-slate-100 disabled:text-slate-400 focus:border-teal-700 focus:outline-none"
                    />
                  </div>
                </div>

                {/* Query Params & Headers */}
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div>
                    <label
                      htmlFor="api-params"
                      className="mb-1.5 block text-xs font-medium text-slate-700"
                    >
                      Query Parameters (one key=value per line)
                    </label>
                    <textarea
                      id="api-params"
                      rows={2}
                      value={formState.paramsText}
                      onChange={(e) =>
                        setFormState((s) => ({
                          ...s,
                          paramsText: e.target.value,
                        }))
                      }
                      placeholder={"country=IN\ncategory=smartphones"}
                      className="w-full rounded-md border border-slate-300 bg-white p-2.5 font-mono text-xs text-slate-900 focus:border-teal-700 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="api-headers"
                      className="mb-1.5 block text-xs font-medium text-slate-700"
                    >
                      Request Headers (one Header=Value per line)
                    </label>
                    <textarea
                      id="api-headers"
                      rows={2}
                      value={formState.headersText}
                      onChange={(e) =>
                        setFormState((s) => ({
                          ...s,
                          headersText: e.target.value,
                        }))
                      }
                      placeholder={"Accept=application/json"}
                      className="w-full rounded-md border border-slate-300 bg-white p-2.5 font-mono text-xs text-slate-900 focus:border-teal-700 focus:outline-none"
                    />
                  </div>
                </div>

                {/* Collapsible JSON Field Mapping */}
                <div className="rounded-md border border-slate-200">
                  <button
                    type="button"
                    onClick={() => setShowAdvancedMapping((v) => !v)}
                    className="flex w-full items-center justify-between bg-slate-50 px-4 py-2.5 text-left text-xs font-medium text-slate-700 hover:bg-slate-100"
                  >
                    <span>
                      Response JSON Field Mappings (maps API payload paths to normalized schema)
                    </span>
                    <span className="font-mono text-teal-700">
                      {showAdvancedMapping ? "Hide Mappings" : "Configure Mappings"}
                    </span>
                  </button>
                  {showAdvancedMapping && (
                    <div className="grid grid-cols-1 gap-3 border-t border-slate-200 p-4 sm:grid-cols-2 lg:grid-cols-4">
                      {FIELD_MAP_LABELS.map((item) => (
                        <div key={item.key}>
                          <label className="mb-1 block text-[11px] font-medium text-slate-600">
                            {item.label}
                          </label>
                          <input
                            type="text"
                            value={formState.field_map[item.key] ?? ""}
                            onChange={(e) =>
                              setFormState((s) => ({
                                ...s,
                                field_map: {
                                  ...s.field_map,
                                  [item.key]: e.target.value,
                                },
                              }))
                            }
                            placeholder={item.placeholder}
                            className="w-full rounded border border-slate-300 bg-white px-2.5 py-1.5 font-mono text-xs text-slate-900 focus:border-teal-700 focus:outline-none"
                          />
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </>
            ) : (
              /* Playwright Target URLs */
              <div>
                <label
                  htmlFor="playwright-urls"
                  className="mb-1.5 block text-xs font-medium text-slate-700"
                >
                  Target Scraper URLs (one URL per line)
                </label>
                <textarea
                  id="playwright-urls"
                  rows={4}
                  required
                  value={formState.playwrightUrlsText}
                  onChange={(e) =>
                    setFormState((s) => ({
                      ...s,
                      playwrightUrlsText: e.target.value,
                    }))
                  }
                  placeholder="https://www.cashify.in/sell-old-mobile-phone/used-apple-iphone-15"
                  className="w-full rounded-md border border-slate-300 bg-white p-3 font-mono text-xs text-slate-900 focus:border-teal-700 focus:outline-none"
                />
              </div>
            )}

            <div className="flex items-center justify-end gap-2 border-t border-slate-200 pt-4">
              <button
                type="button"
                onClick={closeForm}
                className="rounded-md border border-slate-300 bg-white px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="rounded-md bg-teal-700 px-4 py-2 text-xs font-medium text-white hover:bg-teal-800 disabled:opacity-50"
              >
                {saving
                  ? "Saving..."
                  : editingOriginalName
                    ? "Save Changes"
                    : "Create Source"}
              </button>
            </div>
          </form>
        </section>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Left Column: Configured Sources List with Enable/Disable, Edit, Run, Delete */}
        <section className="overflow-hidden rounded-lg border border-slate-200 bg-white lg:col-span-7">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-3.5">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">
                Configured Scraper &amp; API Sources ({filteredSources.length})
              </h2>
              <p className="text-xs text-slate-500">
                {enabledCount} enabled · {disabledCount} disabled · Synced with YAML configs
              </p>
            </div>

            {/* Filter Pills */}
            <div className="inline-flex flex-wrap items-center gap-1 rounded-md border border-slate-200 bg-slate-100 p-0.5 text-xs">
              {(
                [
                  { id: "all", label: `All (${sourceConfigs.length})` },
                  { id: "generic_api", label: `APIs (${apiCount})` },
                  { id: "playwright", label: `Scrapers (${scraperCount})` },
                  { id: "enabled", label: `Enabled (${enabledCount})` },
                  { id: "disabled", label: `Disabled (${disabledCount})` },
                ] as Array<{ id: FilterMode; label: string }>
              ).map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setFilterMode(tab.id)}
                  className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                    filterMode === tab.id
                      ? "bg-white text-slate-900 shadow-2xs"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          <div className="divide-y divide-slate-100">
            {filteredSources.length === 0 ? (
              <div className="px-5 py-10 text-center text-xs text-slate-500">
                No sources match the selected filter. Click &ldquo;Add API Source&rdquo; above to register one.
              </div>
            ) : (
              filteredSources.map((cfg) => {
                const isToggling = togglingName === cfg.name;
                const isRunning = runningSource === cfg.name;
                const isConfirmingDelete = confirmDeleteName === cfg.name;
                return (
                  <div
                    key={cfg.name}
                    className={`px-5 py-4 transition-colors ${
                      cfg.enabled ? "bg-white" : "bg-slate-50/70"
                    }`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={`font-mono text-sm font-semibold ${
                              cfg.enabled
                                ? "text-slate-900"
                                : "text-slate-500 line-through"
                            }`}
                          >
                            {cfg.name}
                          </span>
                          <span
                            className={`inline-flex items-center gap-1 rounded px-2 py-0.5 font-mono text-[11px] font-medium ${
                              cfg.kind === "generic_api"
                                ? "bg-teal-50 text-teal-800 border border-teal-200"
                                : "bg-slate-100 text-slate-700 border border-slate-200"
                            }`}
                          >
                            {cfg.kind === "generic_api" ? "REST API" : "Playwright"}
                          </span>
                          {cfg.side && (
                            <span className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 font-mono text-[11px] uppercase text-slate-600">
                              {cfg.side}
                            </span>
                          )}
                          <span
                            className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-medium ${
                              cfg.enabled
                                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                : "bg-slate-100 text-slate-600 border border-slate-200"
                            }`}
                          >
                            <span
                              className={`h-1.5 w-1.5 rounded-full ${
                                cfg.enabled ? "bg-emerald-600" : "bg-slate-400"
                              }`}
                            />
                            {cfg.enabled ? "Enabled" : "Disabled"}
                          </span>
                        </div>

                        {/* Metadata Details */}
                        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
                          {cfg.kind === "generic_api" && (
                            <>
                              <span className="font-mono">
                                method:{cfg.method ?? "GET"}
                              </span>
                              <span className="font-mono">
                                auth:{cfg.auth_type ?? "none"}
                                {cfg.auth_token_env ? ` (${cfg.auth_token_env})` : ""}
                              </span>
                              <span className="font-mono">
                                page:{cfg.pagination_type ?? "none"}
                              </span>
                              {cfg.items_path && (
                                <span className="font-mono">
                                  items:{cfg.items_path}
                                </span>
                              )}
                            </>
                          )}
                        </div>
                      </div>

                      {/* Controls: Enable/Disable Switch, Run, Edit, Delete */}
                      <div className="flex flex-wrap items-center gap-1.5 shrink-0">
                        <button
                          type="button"
                          disabled={isToggling}
                          onClick={() => void handleToggleEnabled(cfg)}
                          title={cfg.enabled ? "Disable source" : "Enable source"}
                          className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors ${
                            cfg.enabled
                              ? "border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100"
                              : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100"
                          }`}
                        >
                          <Power className="h-3.5 w-3.5" />
                          {isToggling
                            ? "..."
                            : cfg.enabled
                              ? "Disable"
                              : "Enable"}
                        </button>

                        <button
                          type="button"
                          disabled={!cfg.enabled || isRunning}
                          onClick={() => void handleRunSourceScrape(cfg)}
                          title={
                            cfg.enabled
                              ? "Run collection for this source"
                              : "Enable source to run collection"
                          }
                          className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-40"
                        >
                          <Play className="h-3.5 w-3.5 text-teal-700" />
                          {isRunning ? "Running..." : "Run"}
                        </button>

                        <button
                          type="button"
                          onClick={() => openEditForm(cfg)}
                          className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50"
                        >
                          <Edit3 className="h-3.5 w-3.5" />
                          Edit
                        </button>

                        {isConfirmingDelete ? (
                          <div className="inline-flex items-center gap-1 rounded-md border border-rose-300 bg-rose-50 px-2 py-1">
                            <button
                              type="button"
                              onClick={() => void handleDeleteSource(cfg)}
                              className="text-xs font-semibold text-rose-700 hover:underline"
                            >
                              Confirm
                            </button>
                            <button
                              type="button"
                              onClick={() => setConfirmDeleteName(null)}
                              className="text-xs text-slate-500 hover:text-slate-800"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => setConfirmDeleteName(cfg.name)}
                            title="Delete source"
                            className="inline-flex items-center rounded-md border border-slate-200 bg-white p-1.5 text-slate-400 transition-colors hover:border-rose-200 hover:bg-rose-50 hover:text-rose-600"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Target URLs */}
                    <ul className="mt-2.5 space-y-1">
                      {cfg.urls.map((u) => (
                        <li
                          key={u}
                          className="truncate font-mono text-xs text-slate-500"
                        >
                          {u}
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })
            )}
          </div>
        </section>

        {/* Right Column: Recent Scrape Runs */}
        <section className="overflow-hidden rounded-lg border border-slate-200 bg-white lg:col-span-5">
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
                    <td className="px-4 py-2.5 font-mono text-xs text-slate-900">
                      {run.source}
                    </td>
                    <td className="px-4 py-2.5 text-xs font-medium text-emerald-700">
                      {run.status}
                    </td>
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
                {copied ? (
                  <Check className="h-3.5 w-3.5 text-emerald-700" />
                ) : (
                  <Copy className="h-3.5 w-3.5" />
                )}
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
