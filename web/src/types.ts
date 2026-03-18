export type LlmDecision = {
  ts: number;
  ts_iso: string | null;
  symbol: string | null;
  action: string; // "proceed" | "flat" | "flip" | "unknown"
  original_action: string;
  confidence: number; // 0–1
  regime: string;
  notes: string;
  mode: string; // "ADVISORY" | "VETO_ONLY" | etc.
  trigger: string;
  trigger_context: string;
  is_veto: boolean;
  allowed: boolean;
  gate_reason: string;
  would_have_traded: boolean;
  model: string;
  size_multiplier: number | null;
};

export type LlmFeedResponse = {
  items: LlmDecision[];
  total: number;
  has_data: boolean;
};

export type LlmMarketView = {
  has_data: boolean;
  regime: string;
  overall_bias: string; // "bullish" | "neutral" | "volatile" | "mixed"
  avg_confidence: number | null;
  per_symbol: Record<string, LlmDecision>;
  last_updated: string | null;
  summary: string;
  decision_counts: {
    proceed: number;
    flat: number;
    flip: number;
    total_recent: number;
  };
};

export type Strategy = {
  id: string;
  name?: string;
  lastHeartbeat?: string | null;
  lastTradeAt?: string | null;
  pnl_realized?: number | null;
  open_position?: {
    side?: string;
    size?: number;
    avg_entry?: number;
    unrealized_pnl?: number;
    unrealized_pnl_pct?: number;
    updated_at?: string;
  } | null;
};

export type Trade = {
  id: string;
  ts: string;
  pair: string;
  side: string;
  qty: number;
  entry?: number;
  exit?: number;
  fee?: number;
  pnl?: number;
};

export type ActivityEvent = {
  ts: number;
  ts_iso: string | null;
  event_type: string;
  symbol: string | null;
  title: string;
  detail: string;
  scalp_insight: string;
  badge: string;
  badge_color: string;
  data: Record<string, unknown>;
};

export type ActivityFeedResponse = {
  items: ActivityEvent[];
  has_data: boolean;
  sources: { decisions: number; missed_trades: number };
};
