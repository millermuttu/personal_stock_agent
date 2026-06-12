import type {
  AnalysisRunResponse,
  AnalysisRunSummary,
  CreateAnalysisResponse,
  InvestmentsResponse,
  PaperPosition,
  PriceHistoryResponse,
  PriceRange,
  StockSearchResult,
  Timeframe,
} from "./types";
import {
  normalizeAnalysisRun,
  normalizeCreateAnalysisResponse,
  normalizeInvestments,
  normalizePaperPositionResponse,
  normalizePriceHistory,
  normalizeRunSummaries,
  normalizeStockSearchResults,
} from "./normalize";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) {
        detail = body.detail;
      }
    } catch {
      // Fall back to default detail when backend does not return JSON.
    }
    throw new Error(detail);
  }

  return (await response.json()) as T;
}

export function searchStocks(query: string): Promise<StockSearchResult[]> {
  const encoded = encodeURIComponent(query);
  return request<unknown>(`/stocks/search?q=${encoded}`).then(normalizeStockSearchResults);
}

export function createAnalysis(payload: {
  ticker: string;
  timeframe: Timeframe;
}): Promise<CreateAnalysisResponse> {
  return request<unknown>("/analysis", {
    method: "POST",
    body: JSON.stringify(payload),
  }).then(normalizeCreateAnalysisResponse);
}

export function getAnalysis(runId: string): Promise<AnalysisRunResponse> {
  return request<unknown>(`/analysis/${runId}`).then(normalizeAnalysisRun);
}

export function listRuns(limit = 50): Promise<AnalysisRunSummary[]> {
  return request<unknown>(`/analysis?limit=${limit}`).then(normalizeRunSummaries);
}

export function getCandles(ticker: string, range: PriceRange): Promise<PriceHistoryResponse> {
  const encoded = encodeURIComponent(ticker);
  return request<unknown>(`/stocks/${encoded}/candles?range=${range}`).then(normalizePriceHistory);
}

export function listInvestments(): Promise<InvestmentsResponse> {
  return request<unknown>("/investments").then(normalizeInvestments);
}

export function openInvestment(payload: {
  ticker: string;
  amount: number;
  run_id?: string;
}): Promise<PaperPosition> {
  return request<unknown>("/investments", {
    method: "POST",
    body: JSON.stringify(payload),
  }).then(normalizePaperPositionResponse);
}

export function closeInvestment(positionId: string): Promise<PaperPosition> {
  return request<unknown>(`/investments/${positionId}/close`, {
    method: "POST",
  }).then(normalizePaperPositionResponse);
}
