export type NormalizedCondition =
  | "new"
  | "like_new"
  | "excellent"
  | "good"
  | "fair"
  | "poor"
  | "unknown";

export type ExportGranularity = "daily" | "weekly" | "monthly";
export type MarketSide = "buy" | "sell" | "new";

export interface NormalizedPriceRecord {
  side: MarketSide;
  source: string;
  source_product_id: string;
  brand: string;
  model: string;
  storage_gb: number | null;
  ram_gb: number | null;
  color: string | null;
  condition: NormalizedCondition;
  price: number;
  currency: string;
  mrp: number | null;
  discount_pct: number | null;
  in_stock: boolean | null;
  source_url: string;
  captured_at: string;
  run_id: string | number;
  raw_payload: Record<string, unknown>;
}

export interface ScrapeRun {
  id: number;
  source: string;
  started_at: string;
  finished_at: string;
  status: "success" | "blocked" | "failed";
  records_count: number;
  error_message: string | null;
}

export interface SourceConfigSummary {
  name: string;
  kind: "playwright" | "generic_api";
  enabled: boolean;
  urls: string[];
  auth_type?: string;
  pagination_type?: string;
}

export interface OverviewResponse {
  kpis: {
    total_snapshots: number;
    buy_snapshots: number;
    sell_snapshots: number;
    new_snapshots: number;
    unique_models: number;
    sources_count: number;
    latest_captured_at: string | null;
    avg_price: number;
  };
  phones: string[];
  buy_phones: string[];
  sell_phones: string[];
  new_phones: string[];
  sources: string[];
  buy_sources: string[];
  sell_sources: string[];
  new_sources: string[];
  source_configs: SourceConfigSummary[];
  recent_runs: ScrapeRun[];
}

export interface SnapshotsResponse {
  total: number;
  records: NormalizedPriceRecord[];
}

export interface TrendRow {
  brand: string;
  model: string;
  source: string;
  condition: string;
  bucket_date: string;
  avg_price: number;
  min_price: number;
  max_price: number;
  median_price: number;
  dod_abs: number | null;
  dod_pct: number | null;
  wow_abs: number | null;
  wow_pct: number | null;
  mom_abs: number | null;
  mom_pct: number | null;
  ma_7d: number;
  ma_30d: number;
}

export interface ExportArtifact {
  relative_path: string;
  filename: string;
  kind: "snapshots_csv" | "trends_csv" | "manifest_json";
  row_count?: number;
  sha256?: string;
  preview?: string;
}

export interface ExportResponse {
  granularity: ExportGranularity;
  artifacts: ExportArtifact[];
}
