import { useState } from "react";
import { Download, Play, Search, X } from "lucide-react";
import type { MarketSide, NormalizedPriceRecord } from "../types";

interface SnapshotsViewProps {
  activeSide: MarketSide;
  buyCount: number;
  sellCount: number;
  newCount: number;
  partsCount: number;
  records: NormalizedPriceRecord[];
  total: number;
  loading: boolean;
  phones: string[];
  sources: string[];
  partCategories: string[];
  selectedPhone: string;
  selectedSource: string;
  selectedCondition: string;
  selectedPartCategory: string;
  searchQuery: string;
  scraping: boolean;
  scrapeFeedback: string | null;
  onSideChange: (side: MarketSide) => void;
  onPhoneChange: (val: string) => void;
  onSourceChange: (val: string) => void;
  onConditionChange: (val: string) => void;
  onPartCategoryChange: (val: string) => void;
  onSearchChange: (val: string) => void;
  onRunScrape: () => void;
  onQuickExportCsv: () => void;
  onManageSources?: () => void;
}

const CONDITIONS = ["all", "new", "like_new", "excellent", "good", "fair", "poor", "unknown"];

function formatCurrency(value: number | null, currency: string): string {
  if (value === null) return "—";
  const prefix = currency === "INR" ? "₹" : `${currency} `;
  return `${prefix}${value.toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

export function SnapshotsView({
  activeSide,
  buyCount,
  sellCount,
  newCount,
  partsCount,
  records,
  total,
  loading,
  phones,
  sources,
  partCategories,
  selectedPhone,
  selectedSource,
  selectedCondition,
  selectedPartCategory,
  searchQuery,
  scraping,
  scrapeFeedback,
  onSideChange,
  onPhoneChange,
  onSourceChange,
  onConditionChange,
  onPartCategoryChange,
  onSearchChange,
  onRunScrape,
  onQuickExportCsv,
  onManageSources,
}: SnapshotsViewProps) {
  const [inspectRecord, setInspectRecord] = useState<NormalizedPriceRecord | null>(null);

  const isBuy = activeSide === "buy";
  const isSell = activeSide === "sell";
  const isNew = activeSide === "new";
  const isParts = activeSide === "parts";
  const showRetailColumns = isBuy || isNew;

  const tabDescription = isParts
    ? "Official OEM spare parts and repair pricing scraped from Samsung India and Apple India support"
    : isNew
      ? "Brand-new retail devices scraped exclusively from amazon.in and flipkart"
      : isBuy
        ? "Refurbished & renewed listing prices with MRP, discount %, and stock status"
        : "Trade-in & buyback quotes across condition grades and partner API feeds";

  const sideLabel = isParts ? "Parts" : isNew ? "New Devices" : isBuy ? "Buy" : "Sell";

  const columnCount = isParts ? 6 : showRetailColumns ? 8 : 6;

  return (
    <div className="space-y-6">
      {/* Separate Buy / Sell / New Devices / Parts Pricing Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-3">
        <div
          role="tablist"
          aria-label="Market side"
          className="inline-flex flex-wrap items-center gap-1 rounded-lg border border-slate-200 bg-slate-100 p-1"
        >
          <button
            type="button"
            role="tab"
            aria-selected={isBuy}
            onClick={() => onSideChange("buy")}
            className={`rounded-md px-4 py-2 text-sm font-medium transition-colors whitespace-nowrap shrink-0 ${
              isBuy
                ? "bg-white text-slate-900 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Buy · Refurbished{" "}
            <span className="ml-1 font-mono text-xs text-slate-500 tabular-nums">
              ({buyCount})
            </span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={isSell}
            onClick={() => onSideChange("sell")}
            className={`rounded-md px-4 py-2 text-sm font-medium transition-colors whitespace-nowrap shrink-0 ${
              isSell
                ? "bg-white text-slate-900 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Sell · Buyback{" "}
            <span className="ml-1 font-mono text-xs text-slate-500 tabular-nums">
              ({sellCount})
            </span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={isNew}
            onClick={() => onSideChange("new")}
            className={`rounded-md px-4 py-2 text-sm font-medium transition-colors whitespace-nowrap shrink-0 ${
              isNew
                ? "bg-white text-slate-900 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            New Devices · Amazon.in &amp; Flipkart{" "}
            <span className="ml-1 font-mono text-xs text-slate-500 tabular-nums">
              ({newCount})
            </span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={isParts}
            onClick={() => onSideChange("parts")}
            className={`rounded-md px-4 py-2 text-sm font-medium transition-colors whitespace-nowrap shrink-0 ${
              isParts
                ? "bg-white text-slate-900 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Parts Pricing · Samsung &amp; Apple{" "}
            <span className="ml-1 font-mono text-xs text-slate-500 tabular-nums">
              ({partsCount})
            </span>
          </button>
        </div>

        <p className="text-xs text-slate-500">{tabDescription}</p>
      </div>

      {/* Filter & Scraper Control Bar */}
      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-12 md:items-end">
          <div className={isNew ? "md:col-span-4" : "md:col-span-3"}>
            <label htmlFor="phone-select" className="mb-1.5 block text-xs font-medium text-slate-600">
              {isParts ? "Device Model" : "Available Phones"}
            </label>
            <select
              id="phone-select"
              value={selectedPhone}
              onChange={(e) => onPhoneChange(e.target.value)}
              className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-teal-700 focus:outline-none"
            >
              <option value="all">All {sideLabel} Models ({phones.length})</option>
              {phones.map((phone) => (
                <option key={phone} value={phone}>
                  {phone}
                </option>
              ))}
            </select>
          </div>

          <div className={isNew ? "md:col-span-3" : "md:col-span-2"}>
            <div className="mb-1.5 flex items-center justify-between gap-2">
              <label htmlFor="source-select" className="block text-xs font-medium text-slate-600">
                Source
              </label>
              {onManageSources && (
                <button
                  type="button"
                  onClick={onManageSources}
                  className="text-[11px] font-medium text-teal-700 hover:text-teal-800 hover:underline"
                >
                  + Add / Edit API
                </button>
              )}
            </div>
            <select
              id="source-select"
              value={selectedSource}
              onChange={(e) => onSourceChange(e.target.value)}
              className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-teal-700 focus:outline-none"
            >
              <option value="all">
                {isParts
                  ? "Samsung & Apple Official"
                  : isNew
                    ? "Amazon.in & Flipkart"
                    : `All ${sideLabel} Sources`}
              </option>
              {sources.map((src) => (
                <option key={src} value={src}>
                  {src}
                </option>
              ))}
            </select>
          </div>

          {isParts && (
            <div className="md:col-span-2">
              <label htmlFor="part-category-select" className="mb-1.5 block text-xs font-medium text-slate-600">
                Part Category
              </label>
              <select
                id="part-category-select"
                value={selectedPartCategory}
                onChange={(e) => onPartCategoryChange(e.target.value)}
                className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-teal-700 focus:outline-none"
              >
                <option value="all">All Part Types</option>
                {partCategories.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>
          )}

          {!isNew && !isParts && (
            <div className="md:col-span-2">
              <label htmlFor="condition-select" className="mb-1.5 block text-xs font-medium text-slate-600">
                Condition
              </label>
              <select
                id="condition-select"
                value={selectedCondition}
                onChange={(e) => onConditionChange(e.target.value)}
                className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-teal-700 focus:outline-none"
              >
                {CONDITIONS.map((c) => (
                  <option key={c} value={c}>
                    {c === "all" ? "All Conditions" : c.replace("_", " ")}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="md:col-span-2">
            <label htmlFor="snapshot-search" className="mb-1.5 block text-xs font-medium text-slate-600">
              {isParts ? "Search Part or Model" : "Search Model or ID"}
            </label>
            <div className="relative">
              <Search className="pointer-events-none absolute top-2.5 left-3 h-4 w-4 text-slate-400" />
              <input
                id="snapshot-search"
                type="text"
                value={searchQuery}
                onChange={(e) => onSearchChange(e.target.value)}
                placeholder={isParts ? "Display, Battery, GH82..." : "iPhone 15, B0CHX..."}
                className="w-full rounded-md border border-slate-300 bg-white py-2 pr-3 pl-9 text-sm text-slate-900 placeholder:text-slate-400 focus:border-teal-700 focus:outline-none"
              />
            </div>
          </div>

          <div className="flex items-center gap-2 md:col-span-3 md:justify-end">
            <button
              type="button"
              onClick={onRunScrape}
              disabled={scraping}
              className="inline-flex items-center gap-2 rounded-md bg-teal-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-teal-800 disabled:opacity-50 whitespace-nowrap shrink-0"
            >
              <Play className="h-3.5 w-3.5" />
              {scraping ? "Collecting..." : `Scrape ${sideLabel}`}
            </button>
            <button
              type="button"
              onClick={onQuickExportCsv}
              className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 whitespace-nowrap shrink-0"
            >
              <Download className="h-3.5 w-3.5" />
              CSV
            </button>
          </div>
        </div>

        {scrapeFeedback && (
          <p className="mt-3 text-xs text-slate-600">{scrapeFeedback}</p>
        )}
      </section>

      {/* Normalized Snapshots Table */}
      <section className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3.5">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">
              {isParts
                ? "Official Spare Parts & Repair Pricing (Samsung & Apple)"
                : isNew
                  ? "New Devices (Amazon.in & Flipkart)"
                  : isBuy
                    ? "Buy Listings (Refurbished & Renewed)"
                    : "Sell Quotes (Buyback & Trade-In)"}
            </h2>
            <p className="text-xs text-slate-500">
              Showing {records.length} of {total} snapshots · Click any row to inspect raw payload
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              {isParts ? (
                <tr className="border-b border-slate-200 bg-slate-50 text-xs font-medium text-slate-600">
                  <th className="px-4 py-2.5">Device &amp; Part Code</th>
                  <th className="px-4 py-2.5">Source</th>
                  <th className="px-4 py-2.5">Component / Part</th>
                  <th className="px-4 py-2.5 text-right">Official Price</th>
                  <th className="px-4 py-2.5">Service / Coverage</th>
                  <th className="px-4 py-2.5 text-right">Captured (UTC)</th>
                </tr>
              ) : (
                <tr className="border-b border-slate-200 bg-slate-50 text-xs font-medium text-slate-600">
                  <th className="px-4 py-2.5">Device</th>
                  <th className="px-4 py-2.5">Source</th>
                  <th className="px-4 py-2.5">Specs</th>
                  <th className="px-4 py-2.5">Condition</th>
                  <th className="px-4 py-2.5 text-right">
                    {showRetailColumns ? "Selling Price" : "Buyback Offer"}
                  </th>
                  {showRetailColumns && <th className="px-4 py-2.5 text-right">MRP / Disc</th>}
                  {showRetailColumns && <th className="px-4 py-2.5">Availability</th>}
                  <th className="px-4 py-2.5 text-right">Captured (UTC)</th>
                </tr>
              )}
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                Array.from({ length: 6 }).map((_, idx) => (
                  <tr key={idx}>
                    <td colSpan={columnCount} className="px-4 py-3">
                      <div className="h-4 w-full animate-pulse rounded bg-slate-100" />
                    </td>
                  </tr>
                ))
              ) : records.length === 0 ? (
                <tr>
                  <td colSpan={columnCount} className="px-4 py-10 text-center text-sm text-slate-500">
                    No matching {sideLabel.toLowerCase()} snapshots found. Try clearing filters or running a collection pass.
                  </td>
                </tr>
              ) : isParts ? (
                records.map((rec, idx) => {
                  const appleCare = rec.raw_payload?.applecare_plus_fee_inr;
                  const warranty = rec.raw_payload?.warranty ? String(rec.raw_payload.warranty) : "OEM Genuine";
                  return (
                    <tr
                      key={`${rec.source}-${rec.source_product_id}-${idx}`}
                      onClick={() => setInspectRecord(rec)}
                      className="cursor-pointer transition-colors hover:bg-slate-50"
                    >
                      <td className="px-4 py-2.5">
                        <div className="font-medium text-slate-900">
                          {rec.brand} {rec.model}
                        </div>
                        <div className="font-mono text-xs text-slate-500">{rec.source_product_id}</div>
                      </td>
                      <td className="px-4 py-2.5 font-mono text-xs text-slate-700">{rec.source}</td>
                      <td className="px-4 py-2.5">
                        <div className="text-sm font-medium text-slate-900">{rec.part_name ?? "OEM Part"}</div>
                        <div className="text-xs text-slate-500">{rec.part_category ?? "Component"}</div>
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono font-medium text-slate-900 tabular-nums">
                        <div>{formatCurrency(rec.price, rec.currency)}</div>
                        {rec.mrp && (
                          <div className="text-xs font-normal text-slate-500">
                            MRP {formatCurrency(rec.mrp, rec.currency)}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-xs text-slate-600">
                        <div>{warranty}</div>
                        {typeof appleCare === "number" && (
                          <div className="font-mono text-slate-500 tabular-nums">
                            AppleCare+ fee: {formatCurrency(appleCare, rec.currency)}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono text-xs text-slate-500 tabular-nums">
                        {rec.captured_at.slice(0, 16).replace("T", " ")}
                      </td>
                    </tr>
                  );
                })
              ) : (
                records.map((rec, idx) => (
                  <tr
                    key={`${rec.source}-${rec.source_product_id}-${rec.condition}-${rec.storage_gb ?? 0}-${idx}`}
                    onClick={() => setInspectRecord(rec)}
                    className="cursor-pointer transition-colors hover:bg-slate-50"
                  >
                    <td className="px-4 py-2.5">
                      <div className="font-medium text-slate-900">
                        {rec.brand} {rec.model}
                      </div>
                      <div className="font-mono text-xs text-slate-500">{rec.source_product_id}</div>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs text-slate-700">{rec.source}</td>
                    <td className="px-4 py-2.5 text-xs text-slate-600 tabular-nums">
                      {[
                        rec.storage_gb ? `${rec.storage_gb} GB` : null,
                        rec.ram_gb ? `${rec.ram_gb} GB RAM` : null,
                        rec.color,
                      ]
                        .filter(Boolean)
                        .join(" · ") || "—"}
                    </td>
                    <td className="px-4 py-2.5 text-xs font-medium text-slate-700">
                      {rec.condition.replace("_", " ")}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono font-medium text-slate-900 tabular-nums">
                      {formatCurrency(rec.price, rec.currency)}
                    </td>
                    {showRetailColumns && (
                      <td className="px-4 py-2.5 text-right font-mono text-xs text-slate-600 tabular-nums">
                        {rec.mrp ? (
                          <span>
                            {formatCurrency(rec.mrp, rec.currency)}
                            {rec.discount_pct !== null ? ` (-${rec.discount_pct}%)` : ""}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                    )}
                    {showRetailColumns && (
                      <td className="px-4 py-2.5 text-xs text-slate-600">
                        {rec.in_stock === true ? (
                          <span className="text-emerald-700">In stock</span>
                        ) : rec.in_stock === false ? (
                          <span className="text-rose-700">Out of stock</span>
                        ) : (
                          "—"
                        )}
                      </td>
                    )}
                    <td className="px-4 py-2.5 text-right font-mono text-xs text-slate-500 tabular-nums">
                      {rec.captured_at.slice(0, 16).replace("T", " ")}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Raw Payload Inspector Modal */}
      {inspectRecord && (
        <div className="fixed inset-0 z-50 flex items-center justify-end bg-slate-900/30">
          <div className="flex h-full w-full max-w-xl flex-col border-l border-slate-200 bg-white">
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">
                  {inspectRecord.brand} {inspectRecord.model}
                  {inspectRecord.part_name ? ` — ${inspectRecord.part_name}` : ""}
                </h3>
                <p className="text-xs text-slate-500">
                  {inspectRecord.side.toUpperCase()} · {inspectRecord.source}
                  {inspectRecord.part_category ? ` · ${inspectRecord.part_category}` : ` · ${inspectRecord.condition}`}
                  {" · "}Run #{inspectRecord.run_id}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setInspectRecord(null)}
                className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-900"
                aria-label="Close raw payload inspector"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-5">
              <div className="mb-4 text-xs text-slate-600">
                Source URL:{" "}
                <span className="font-mono break-all text-slate-800">{inspectRecord.source_url}</span>
              </div>
              <div className="mb-2 text-xs font-medium text-slate-700">Raw Payload JSONB</div>
              <pre className="overflow-x-auto rounded-md border border-slate-200 bg-slate-50 p-4 font-mono text-xs text-slate-800">
                {JSON.stringify(inspectRecord.raw_payload, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
