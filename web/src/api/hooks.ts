// One TanStack Query hook per endpoint. Components never call client.ts directly.
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { get, post, del } from './client'
import type {
  Summary,
  PlanRow,
  Trace,
  CycleRow,
  Graph,
  BeliefNode,
  CompoundingPoint,
  Validation,
  LlmStatus,
  Explain,
  AskRequest,
  AskResponse,
  Absence,
  NotePreview,
  TrustTrajectory,
  Synthetic,
  StaffingPoint,
} from './types'

export const useSummary = () =>
  useQuery({ queryKey: ['summary'], queryFn: () => get<Summary>('/api/summary') })

// Polls so absences reported in Discord show up in the plan within a few seconds.
export const useCurrentPlan = () =>
  useQuery({
    queryKey: ['plan', 'current'],
    queryFn: () => get<PlanRow[]>('/api/plan/current'),
    refetchInterval: 4000,
  })

export const useAbsences = () =>
  useQuery({
    queryKey: ['absences'],
    queryFn: () => get<Absence[]>('/api/absences'),
    refetchInterval: 4000,
  })

// Mirrors api/cost.py: shortfall premium + SLA penalty beyond the 2.0 tolerance (for optimistic UI).
function riskEur(short: number): number {
  if (short <= 0) return 0
  return Math.round(short * 41.4 + Math.max(0, short - 2) * 600)
}

// Optimistic resolve: the day card flips the instant you click, then reconciles with the server.
// 'filled' restores cover (day goes green); 'accepted' keeps the gap counted (stays short).
export const useResolveAbsence = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, option }: { id: number; date: string; option: 'filled' | 'accepted' }) =>
      post<Absence>(`/api/absences/${id}/resolve`, { option }),
    onMutate: async ({ id, date, option }) => {
      await qc.cancelQueries({ queryKey: ['absences'] })
      await qc.cancelQueries({ queryKey: ['plan', 'current'] })
      const prevAbsences = qc.getQueryData<Absence[]>(['absences'])
      const prevPlan = qc.getQueryData<PlanRow[]>(['plan', 'current'])

      const nextAbsences = (prevAbsences ?? []).map((a) =>
        a.id === id ? { ...a, status: 'resolved' as const, resolution: option } : a,
      )
      qc.setQueryData(['absences'], nextAbsences)

      // recompute coverage for this date from the optimistic absence state
      const effective = nextAbsences.filter(
        (a) => a.date === date && (a.status === 'open' || a.resolution === 'accepted'),
      ).length
      qc.setQueryData<PlanRow[]>(['plan', 'current'], (rows) =>
        (rows ?? []).map((r) => {
          if (r.date !== date) return r
          const confirmed = Math.max(0, r.target_headcount - effective)
          const short = r.target_headcount - confirmed
          return {
            ...r,
            confirmed_headcount: confirmed,
            coverage: short > 0 ? 'short' : 'covered',
            short_by: short,
            sla_risk_eur: riskEur(short),
          }
        }),
      )
      return { prevAbsences, prevPlan }
    },
    onError: (_e, _vars, ctx) => {
      if (ctx?.prevAbsences) qc.setQueryData(['absences'], ctx.prevAbsences)
      if (ctx?.prevPlan) qc.setQueryData(['plan', 'current'], ctx.prevPlan)
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['absences'] })
      qc.invalidateQueries({ queryKey: ['plan', 'current'] })
    },
  })
}

export const useClearAbsences = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => del<{ status: string }>('/api/absences'),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['absences'] })
      qc.invalidateQueries({ queryKey: ['plan', 'current'] })
    },
  })
}

export const useTrace = (date: string | null) =>
  useQuery({
    queryKey: ['trace', date],
    queryFn: () => get<Trace>(`/api/plan/${date}/trace`),
    enabled: !!date,
  })

export const useCycles = () =>
  useQuery({ queryKey: ['cycles'], queryFn: () => get<CycleRow[]>('/api/cycles') })

export const useGraph = (asOf: string | null) =>
  useQuery({
    queryKey: ['graph', asOf],
    queryFn: () => get<Graph>(asOf ? `/api/graph?as_of=${asOf}` : '/api/graph'),
  })

export const useBelief = (id: string | null) =>
  useQuery({
    queryKey: ['belief', id],
    queryFn: () => get<BeliefNode>(`/api/beliefs/${id}`),
    enabled: !!id,
  })

export const useCompounding = () =>
  useQuery({ queryKey: ['compounding'], queryFn: () => get<CompoundingPoint[]>('/api/compounding') })

export const useValidation = () =>
  useQuery({ queryKey: ['validation'], queryFn: () => get<Validation>('/api/validation') })

export const useTrust = () =>
  useQuery({ queryKey: ['trust'], queryFn: () => get<TrustTrajectory>('/api/trust') })

export const useSynthetic = () =>
  useQuery({ queryKey: ['synthetic'], queryFn: () => get<Synthetic>('/api/synthetic') })

export const useStaffing = () =>
  useQuery({ queryKey: ['staffing'], queryFn: () => get<StaffingPoint[]>('/api/staffing') })

export const useLlmStatus = () =>
  useQuery({ queryKey: ['llm', 'status'], queryFn: () => get<LlmStatus>('/api/llm/status') })

export const useExplain = (date: string | null) =>
  useQuery({
    queryKey: ['explain', date],
    queryFn: () => get<Explain>(`/api/plan/${date}/explain`),
    enabled: !!date,
  })

export const useAsk = () =>
  useMutation({ mutationFn: (req: AskRequest) => post<AskResponse>('/api/ask', req) })

// Planner-note capture: preview = AI interpretation (no save); commit = add candidate to the graph.
export const useNotePreview = () =>
  useMutation({
    mutationFn: (body: { text: string; author?: string }) =>
      post<NotePreview>('/api/notes/preview', body),
  })

export const useCommitNote = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { text: string; author?: string; parsed?: Record<string, unknown> | null }) =>
      post<BeliefNode>('/api/notes', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['graph'] }),
  })
}

export const useDeleteNote = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => del<{ status: string }>(`/api/notes/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['graph'] }),
  })
}
