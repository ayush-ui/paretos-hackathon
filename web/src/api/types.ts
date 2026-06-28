// TypeScript mirror of api/schemas.py — verified against live JSON from the running server.
// If a Pydantic model changes, update here in lockstep.

export interface Breakdown {
  total: number
  overstaff_cost: number
  understaff_premium_cost: number
  sla_penalty_cost: number
  overstaffed_days: number
  understaffed_days: number
  sla_breach_days: number
}

export interface Summary {
  n_days: number
  baseline_cost: number
  engine_cost: number
  b1_flat_cost: number
  b2_adaptive_cost: number
  engine_gap_closed_pct: number
  b2_gap_closed_pct: number
  saving_vs_baseline_eur: number
  breakdown: Breakdown
}

export type Confidence = 'high' | 'medium' | 'low'

export interface PlanRow {
  date: string
  weekday: string
  decision_date: string
  planned: number
  recommended: number
  // product translation layer (1 person-day = 1 person on 1 shift/day)
  target_headcount: number
  optimiser_headcount: number
  confirmed_headcount: number
  coverage: 'covered' | 'short'
  short_by: number
  sla_risk_eur: number
  confidence: Confidence
  confidence_basis: string
  reason_short: string
  est_saving_eur: number
  trim_pct: number
}

export interface Trace {
  date: string
  recommended: number
  regime_boundary: string | null
  history_ratios: Record<string, number>
  k: number
  level: number
  offset: number
  trend_adj: number
  planned: number
  actual: number | null
  our_cost: number | null
  baseline_cost: number | null
  is_holdout: boolean
  reason_text: string
}

export interface CycleRow {
  decision_date: string
  days: number
  engine_cost: number
  baseline_cost: number
  gap_closed_pct: number
}

export type BeliefStatus = 'active' | 'candidate' | 'retired'

export interface BeliefNode {
  id: string
  kind: string
  status: BeliefStatus
  trust: number
  activities: string[]
  scope: string
  valid_from: string
  valid_to: string | null
  author: string | null
  note: string
  contribution_eur: number
  evidence: string[]
}

export type EdgeKind = 'supersedes' | 'contradicts' | 'reaffirms' | 'refines'

export interface GraphEdge {
  src: string
  dst: string
  kind: string
}

export interface Graph {
  as_of: string | null
  nodes: BeliefNode[]
  edges: GraphEdge[]
}

export interface CompoundingPoint {
  decision_date: string
  statuses: Record<string, string>
  cycle_cost: number
  cycle_baseline: number
  cum_gap_pct: number
}

export interface AblationRow {
  id: string
  contribution_eur: number
}

export interface Validation {
  ablation: AblationRow[]
  sensitivity: Record<string, number>
  noise_floor: Record<string, number>
}

export interface Absence {
  id: number
  worker: string
  date: string
  reason: string
  source: string
  status: 'open' | 'resolved'
  resolution: string | null
  created_at: string
}

export interface AbsenceImpact {
  absence: Absence
  date: string
  weekday: string
  target_headcount: number
  confirmed_headcount: number
  short_by: number
  sla_risk_eur: number
  sla_breach: boolean
  recommendation: string
  message: string
}

export interface NoteInterpretation {
  scope: string
  kind: string
  summary: string
  is_one_off: boolean
  confidence: number
  influence_note: string
}

export interface NotePreview {
  interpretation: NoteInterpretation
  parsed: Record<string, unknown> | null
  raw_text: string
  author: string | null
  note_id: string
  llm_used: boolean
}

export interface LlmStatus {
  available: boolean
  model: string
}

// --- provenance KG (Source/Belief/Decision/Outcome ontology) ---
export type ProvenanceNodeType = 'source' | 'belief' | 'decision' | 'outcome'

export interface ProvenanceNode {
  id: string
  type: ProvenanceNodeType
  label?: string
  // belief
  status?: string
  trust?: number
  scope?: string
  note?: string
  valid_from?: string
  valid_to?: string | null
  kind?: string
  // decision
  week?: string
  plan_total?: number
  k?: number
  n_days?: number
  // outcome
  cost?: number
  baseline_cost?: number
  gap_closed_pct?: number
  hue?: number
  is_forecast?: boolean
}

export type ProvenanceEdgeType =
  | 'SOURCED_FROM'
  | 'INFORMED'
  | 'CONSIDERED'
  | 'RESULTED_IN'
  | 'UPDATED'
  | 'PRECEDED'
  | 'CONTRADICTS'

export interface ProvenanceEdge {
  src: string
  dst: string
  type: ProvenanceEdgeType
  delta?: number
}

export interface Provenance {
  as_of?: string | null
  nodes: ProvenanceNode[]
  edges: ProvenanceEdge[]
  counts: Record<string, number>
}

export interface ProvenanceTraceBelief {
  belief: string
  trust: number | null
  scope: string | null
  note: string | null
  role: 'INFORMED' | 'CONSIDERED'
  source: string | null
}

export interface ProvenanceTrace {
  week: string
  decision: ProvenanceNode | null
  informed_by: ProvenanceTraceBelief[]
  outcome: ProvenanceNode | null
}

// --- shadow-trust trajectory ---
export interface TrustPoint {
  week: string
  trust: number
  helped: number
  delta_eur: number
  n_days: number
  status: string
}

export interface TrustSummary {
  final_trust: number
  weeks: number
  peak_trust: number
  ever_helped: boolean
  ever_hurt: boolean
}

export interface TrustTrajectory {
  trajectories: Record<string, TrustPoint[]>
  summary: Record<string, TrustSummary>
  params: { alpha: number; init_trust: number; help_threshold: number }
}

// --- staffing person-days over time ---
export interface StaffingPoint {
  week: string
  label: string
  planned_pd: number
  optimiser_pd: number
  actual_pd: number | null
  is_holdout: boolean
}

// --- synthetic stress-test ---
export interface SyntheticWorld {
  world: string
  story: string
  n_days: number
  optimiser_cost: number
  engine_cost: number
  naive_cost: number
  flat_trim_cost: number
  engine_gap_pct: number
  naive_gap_pct: number
  flat_trim_gap_pct: number
  engine_beats_naive: boolean
  engine_mae: number
  understaffed: number
}

export interface Synthetic {
  worlds: SyntheticWorld[]
  note: string
}

export interface Explain {
  date: string
  text: string
  llm_used: boolean
}

export interface AskRequest {
  date: string
  question: string
}

export interface AskResponse {
  date: string
  question: string
  answer: string
  llm_used: boolean
}
