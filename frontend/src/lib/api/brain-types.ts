export interface BrainStrategy {
  strategy_id: string;
  version_id: string;
  version: number;
  name: string;
  status: string;
  enabled: boolean;
  execution_permission: string;
  spec: { symbol: string; direction: string; trigger_timeframe: string; parameters: Record<string, unknown> };
}
export interface BrainSetup {
  setup_id: string;
  strategy_version_id: string;
  state: string;
  symbol?: string;
  instrument: string;
  direction: string;
  stage: string;
  observed_at: string;
  expires_at: string;
  freshness: string;
  fresh_until: string;
  risk_state: string;
  reason_codes: string[];
  evidence_reference: string;
  evidence: Record<string, string>;
  candidate_id: string | null;
  decision_id: string | null;
  journal: { id: string; status: string; net_pnl: string | null } | null;
  quality_components: Record<string, string>;
  entry: string | null;
  stop: string | null;
  targets: string[];
  history?: Array<{ record_id: string; kind: string; occurred_at: string; payload: Record<string, unknown> }>;
}
export interface BrainOverview {
  watched_symbols: string[];
  strategies: BrainStrategy[];
  setups: BrainSetup[];
  limitations: string[];
  paper_only: boolean;
}
