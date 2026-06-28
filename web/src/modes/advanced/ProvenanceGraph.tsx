import { useMemo, useState } from 'react'
import ReactFlow, { Background, Controls, MarkerType } from 'reactflow'
import type { Node, Edge } from 'reactflow'
import 'reactflow/dist/style.css'
import type { ProvenanceNode, ProvenanceEdge } from '../../api/types'
import { useProvenance } from '../../api/hooks'
import { color, statusColor } from '../../theme/theme'
import { PanelLoader } from '../../components/Loader'
import styles from './ProvenanceGraph.module.css'

// Two layouts, both legible:
//   • structured — fixed lanes Sources → Beliefs → Decisions → Outcomes (clean, scannable)
//   • organic    — a force-directed spring layout (the "knowledge graph" feel; related nodes cluster)
// Edges are labelled. Click a NODE to focus its neighbourhood, or click an EDGE to light up its whole
// reasoning flow (source → belief → decision → € outcome); everything else fades.

type Layout = 'structured' | 'organic'

const COL_X: Record<string, number> = { source: 0, belief: 250, decision: 560, outcome: 800 }
const COL_LABEL: Record<string, string> = {
  source: 'Sources', belief: 'Beliefs', decision: 'Decisions (weeks)', outcome: 'Outcomes (€)',
}
const ROW = 66

const EDGE_STYLE: Record<string, { stroke: string; dashed?: boolean; label: string }> = {
  SOURCED_FROM: { stroke: color.black40, dashed: true, label: 'from note' },
  INFORMED: { stroke: color.violet, label: 'informed' },
  CONSIDERED: { stroke: color.black20, dashed: true, label: 'considered' },
  RESULTED_IN: { stroke: color.green, label: 'result €' },
  UPDATED: { stroke: color.turq, label: 'Δ trust' },
  PRECEDED: { stroke: color.black20, dashed: true, label: 'next week' },
  CONTRADICTS: { stroke: color.red, dashed: true, label: 'contradicts' },
}
const DEFAULT_ON: Record<string, boolean> = {
  SOURCED_FROM: true, INFORMED: true, RESULTED_IN: true,
  CONSIDERED: false, UPDATED: false, PRECEDED: false, CONTRADICTS: true,
}
const FILTERS: { key: string; label: string }[] = [
  { key: 'INFORMED', label: 'informed' },
  { key: 'RESULTED_IN', label: 'result €' },
  { key: 'SOURCED_FROM', label: 'from note' },
  { key: 'CONTRADICTS', label: 'contradicts' },
  { key: 'CONSIDERED', label: 'considered' },
  { key: 'UPDATED', label: 'trust updates' },
  { key: 'PRECEDED', label: 'week → week' },
]

function outcomeColor(n: ProvenanceNode): string {
  if (n.is_forecast) return color.dataSlate
  const hue = n.hue ?? 0
  return hue >= 0.8 ? color.green : hue >= 0.5 ? color.yellow : color.red
}
function nodeColor(n: ProvenanceNode): string {
  if (n.type === 'source') return color.black60
  if (n.type === 'belief') return statusColor[n.status ?? 'candidate'] ?? color.black40
  if (n.type === 'decision') return color.violet
  return outcomeColor(n)
}
function nodeBody(n: ProvenanceNode) {
  if (n.type === 'source') return <span className={styles.srcLabel}>{n.label}</span>
  if (n.type === 'belief')
    return (
      <div className={styles.beliefBody}>
        <span className={styles.bId}>{n.label}</span>
        <span className={styles.bScope}>{n.scope}</span>
        <span className={styles.bTrust}>trust {Math.round((n.trust ?? 0) * 100)}%</span>
      </div>
    )
  if (n.type === 'decision')
    return (
      <div className={styles.decBody}>
        <span className={styles.decWk}>{n.week?.slice(5)}</span>
        <span className={styles.decPd}>{n.plan_total} pd</span>
      </div>
    )
  return <span className={styles.outLabel}>{n.is_forecast ? 'forecast' : `€${n.cost}`}</span>
}

// deterministic Fruchterman-Reingold spring layout (no deps, no randomness → stable each render)
function organicLayout(nodes: ProvenanceNode[], edges: ProvenanceEdge[]): Map<string, { x: number; y: number }> {
  const ids = nodes.map((n) => n.id)
  const N = ids.length || 1
  const pos = new Map<string, { x: number; y: number }>()
  ids.forEach((id, i) => {
    const a = (i / N) * Math.PI * 2 // seed on a ring by index (deterministic)
    pos.set(id, { x: Math.cos(a) * 450 + (i % 9) * 3, y: Math.sin(a) * 450 + (i % 7) * 3 })
  })
  const k = Math.sqrt((1300 * 950) / N)
  let temp = 130
  for (let it = 0; it < 320; it++) {
    const disp = new Map(ids.map((id) => [id, { x: 0, y: 0 }]))
    for (let i = 0; i < ids.length; i++) {
      for (let j = i + 1; j < ids.length; j++) {
        const a = pos.get(ids[i])!, b = pos.get(ids[j])!
        const dx = a.x - b.x, dy = a.y - b.y
        const d = Math.hypot(dx, dy) || 0.01
        const f = (k * k) / d
        const ux = dx / d, uy = dy / d
        disp.get(ids[i])!.x += ux * f; disp.get(ids[i])!.y += uy * f
        disp.get(ids[j])!.x -= ux * f; disp.get(ids[j])!.y -= uy * f
      }
    }
    for (const e of edges) {
      const a = pos.get(e.src), b = pos.get(e.dst)
      if (!a || !b) continue
      const dx = a.x - b.x, dy = a.y - b.y
      const d = Math.hypot(dx, dy) || 0.01
      const f = (d * d) / k
      const ux = dx / d, uy = dy / d
      disp.get(e.src)!.x -= ux * f; disp.get(e.src)!.y -= uy * f
      disp.get(e.dst)!.x += ux * f; disp.get(e.dst)!.y += uy * f
    }
    for (const id of ids) {
      const dd = disp.get(id)!, p = pos.get(id)!
      const d = Math.hypot(dd.x, dd.y) || 0.01
      p.x += (dd.x / d) * Math.min(d, temp)
      p.y += (dd.y / d) * Math.min(d, temp)
    }
    temp *= 0.975
  }
  return pos
}

export function ProvenanceGraph({ asOf, onSelectBelief }: {
  asOf: string | null
  onSelectBelief: (id: string) => void
}) {
  const { data } = useProvenance(asOf)
  const [layout, setLayout] = useState<Layout>('structured')
  const [edgeOn, setEdgeOn] = useState<Record<string, boolean>>(DEFAULT_ON)
  const [focusSet, setFocusSet] = useState<Set<string> | null>(null)
  const [focusPrimary, setFocusPrimary] = useState<string | null>(null)

  const organic = useMemo(
    () => (data ? organicLayout(data.nodes, data.edges) : new Map<string, { x: number; y: number }>()),
    [data],
  )

  // structured lane positions
  const structured = useMemo(() => {
    const m = new Map<string, { x: number; y: number }>()
    if (!data) return m
    const decisions = data.nodes.filter((n) => n.type === 'decision').sort((a, b) =>
      (a.week ?? '').localeCompare(b.week ?? ''))
    const weekRow = new Map(decisions.map((n, i) => [n.week, i]))
    const H = Math.max(decisions.length, 1) * ROW
    const spread = (items: ProvenanceNode[], x: number) =>
      items.forEach((n, i) => m.set(n.id, { x, y: items.length > 1 ? (i * H) / (items.length - 1) : H / 2 }))
    spread(data.nodes.filter((n) => n.type === 'source'), COL_X.source)
    spread(data.nodes.filter((n) => n.type === 'belief'), COL_X.belief)
    data.nodes.filter((n) => n.type === 'decision').forEach((n) =>
      m.set(n.id, { x: COL_X.decision, y: (weekRow.get(n.week) ?? 0) * ROW }))
    data.nodes.filter((n) => n.type === 'outcome').forEach((n) =>
      m.set(n.id, { x: COL_X.outcome, y: (weekRow.get(n.week) ?? 0) * ROW }))
    return m
  }, [data])

  // the full reasoning flow that an edge belongs to: source → belief → decision → € outcome
  function flowFromEdge(e: ProvenanceEdge): Set<string> {
    if (!data) return new Set()
    const have = new Set(data.nodes.map((n) => n.id))
    const F = new Set<string>([e.src, e.dst])
    const add = (id?: string) => { if (id && have.has(id)) F.add(id) }
    const week = (id: string) => id.split(':')[1]
    const outOf = (decId: string) => `outcome:${week(decId)}`
    const decOf = (outId: string) => `decision:${week(outId)}`
    const sourcesOf = (b: string) => data.edges.filter((x) => x.type === 'SOURCED_FROM' && x.src === b).map((x) => x.dst)
    const informersOf = (d: string) => data.edges.filter((x) => x.type === 'INFORMED' && x.dst === d).map((x) => x.src)
    const informedBy = (b: string) => data.edges.filter((x) => x.type === 'INFORMED' && x.src === b).map((x) => x.dst)
    if (e.type === 'INFORMED') { sourcesOf(e.src).forEach(add); add(outOf(e.dst)) }
    else if (e.type === 'RESULTED_IN') { informersOf(e.src).forEach((b) => { add(b); sourcesOf(b).forEach(add) }) }
    else if (e.type === 'SOURCED_FROM') { informedBy(e.src).forEach((d) => { add(d); add(outOf(d)) }) }
    else if (e.type === 'UPDATED') { add(decOf(e.src)); sourcesOf(e.dst).forEach(add) }
    else if (e.type === 'PRECEDED') { add(outOf(e.src)); add(outOf(e.dst)) }
    else if (e.type === 'CONTRADICTS') { sourcesOf(e.src).forEach(add); sourcesOf(e.dst).forEach(add) }
    return F
  }

  function neighborhood(id: string): Set<string> {
    const set = new Set<string>([id])
    if (!data) return set
    for (const e of data.edges) {
      if (e.src === id) set.add(e.dst)
      if (e.dst === id) set.add(e.src)
    }
    return set
  }

  const nodes: Node[] = useMemo(() => {
    if (!data) return []
    const pos = layout === 'organic' ? organic : structured
    const dim = (id: string) => !!focusSet && !focusSet.has(id)
    const widthFor = (t: string) => (t === 'belief' ? 150 : t === 'source' ? 130 : t === 'decision' ? 92 : 64)

    const headers: Node[] = layout === 'structured'
      ? Object.keys(COL_X).map((t) => ({
          id: `__hdr_${t}`,
          position: { x: COL_X[t], y: -56 },
          draggable: false,
          selectable: false,
          data: { label: <div className={styles.colHead}>{COL_LABEL[t]}</div> },
          style: { width: 150, border: 'none', background: 'transparent', boxShadow: 'none', padding: 0 },
        }))
      : []

    const dataNodes: Node[] = data.nodes.map((n) => {
      const c = nodeColor(n)
      const isPrimary = focusPrimary === n.id
      return {
        id: n.id,
        position: pos.get(n.id) ?? { x: 0, y: 0 },
        data: { label: nodeBody(n) },
        style: {
          width: widthFor(n.type),
          fontSize: 10,
          borderRadius: n.type === 'outcome' || n.type === 'source' ? 14 : 7,
          border: `${isPrimary ? 2 : 1}px solid ${isPrimary ? color.violet : c}`,
          background: n.type === 'belief' || n.type === 'decision' ? color.white : `${c}1a`,
          color: color.black,
          padding: n.type === 'belief' ? 6 : 4,
          opacity: dim(n.id) ? 0.1 : 1,
          boxShadow: isPrimary ? '0 0 0 3px rgba(95,38,224,0.18)' : 'none',
          transition: 'opacity 0.15s',
        },
      }
    })
    return [...headers, ...dataNodes]
  }, [data, layout, organic, structured, focusSet, focusPrimary])

  const edges: Edge[] = useMemo(() => {
    if (!data) return []
    // when a focus is active, show every link *inside* the focused set (ignore filters → full chain);
    // otherwise show the link types enabled in the toolbar.
    const visible = focusSet
      ? data.edges.filter((e) => focusSet.has(e.src) && focusSet.has(e.dst))
      : data.edges.filter((e) => edgeOn[e.type])
    return visible.map((e, i) => {
      const s = EDGE_STYLE[e.type] ?? { stroke: color.black40, label: e.type }
      const lbl = e.type === 'UPDATED' && e.delta != null ? `Δ${e.delta > 0 ? '+' : ''}${e.delta}` : s.label
      return {
        id: `e${i}-${e.src}-${e.dst}-${e.type}`,
        source: e.src,
        target: e.dst,
        type: 'smoothstep',
        data: { kind: e.type, src: e.src, dst: e.dst },
        label: lbl,
        labelStyle: { fontSize: 9, fill: s.stroke, fontWeight: 500 },
        labelBgStyle: { fill: color.white, fillOpacity: 0.85 },
        labelBgPadding: [3, 1] as [number, number],
        animated: !!focusSet && (e.type === 'INFORMED' || e.type === 'RESULTED_IN'),
        style: { stroke: s.stroke, strokeWidth: 1.3, strokeDasharray: s.dashed ? '4 3' : undefined },
        markerEnd: { type: MarkerType.ArrowClosed, color: s.stroke, width: 12, height: 12 },
      }
    })
  }, [data, edgeOn, focusSet])

  if (!data) return <PanelLoader label="Building the provenance graph…" />

  const clearFocus = () => { setFocusSet(null); setFocusPrimary(null) }

  return (
    <div className={styles.wrap}>
      <div className={styles.toolbar}>
        <div className={styles.layoutToggle}>
          <button className={`${styles.layoutBtn} ${layout === 'structured' ? styles.layoutOn : ''}`}
            onClick={() => setLayout('structured')}>Structured</button>
          <button className={`${styles.layoutBtn} ${layout === 'organic' ? styles.layoutOn : ''}`}
            onClick={() => setLayout('organic')}>Organic</button>
        </div>
        <span className={styles.divider} />
        <span className={styles.toolLabel}>links:</span>
        {FILTERS.map((f) => (
          <button key={f.key}
            className={`${styles.chip} ${edgeOn[f.key] ? styles.chipOn : ''}`}
            style={edgeOn[f.key] ? { borderColor: EDGE_STYLE[f.key].stroke, color: EDGE_STYLE[f.key].stroke } : undefined}
            onClick={() => setEdgeOn((s) => ({ ...s, [f.key]: !s[f.key] }))}>
            {f.label}
          </button>
        ))}
        <span className={styles.spacer} />
        {focusSet ? (
          <button className={styles.clear} onClick={clearFocus}>✕ clear focus</button>
        ) : (
          <span className={styles.hint}>click a node or an edge to focus its flow</span>
        )}
      </div>

      <div className={styles.canvas}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          fitViewOptions={{ padding: 0.12 }}
          minZoom={0.1}
          nodesDraggable={layout === 'organic'}
          nodesConnectable={false}
          onPaneClick={clearFocus}
          onEdgeClick={(_e, ed) => {
            const d = ed.data as { kind: string; src: string; dst: string } | undefined
            if (!d) return
            setFocusSet(flowFromEdge({ src: d.src, dst: d.dst, type: d.kind as ProvenanceEdge['type'] }))
            setFocusPrimary(null)
          }}
          onNodeClick={(_e, n) => {
            if (n.id.startsWith('__hdr')) return
            setFocusSet(neighborhood(n.id))
            setFocusPrimary(n.id)
            if (n.id.startsWith('belief:')) onSelectBelief(n.id.slice('belief:'.length))
          }}
          proOptions={{ hideAttribution: true }}
        >
          <Background color={color.black20} gap={22} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>

      <div className={styles.legend}>
        <span><i style={{ background: color.black60 }} /> source</span>
        <span><i style={{ background: color.violet }} /> belief / decision</span>
        <span><i style={{ background: color.green }} /> good outcome</span>
        <span><i style={{ background: color.red }} /> costly outcome</span>
        <span><i style={{ background: color.dataSlate }} /> forecast (Oct)</span>
        <span className={styles.note}>
          {data.counts.source ?? 0} sources · {data.counts.belief ?? 0} beliefs ·{' '}
          {data.counts.decision ?? 0} weeks · {data.counts.outcome ?? 0} outcomes
        </span>
      </div>
    </div>
  )
}
