import { useMemo } from 'react'
import ReactFlow, { Background, Controls, MarkerType } from 'reactflow'
import type { Node, Edge } from 'reactflow'
import 'reactflow/dist/style.css'
import type { Graph } from '../../api/types'
import { color, statusColor } from '../../theme/theme'
import styles from './BeliefGraph.module.css'

// Layout: three vertical COLUMNS by lifecycle status (active | candidate | retired). Within a column,
// time runs top→bottom by capture date. This keeps the graph compact horizontally (3 columns, no long
// horizontal scroll) and grows downward as more notes accrue — and the arrows between columns show how
// one note supersedes / contradicts / reaffirms another. A node migrates to the "retired" column when
// the time-slider reaches the week it was retired.
const STATUS_COL: Record<string, number> = { active: 0, candidate: 1, retired: 2 }
const COL_X = 240
const ROW_Y = 120
const COL_LABEL: Record<string, string> = { active: 'Active', candidate: 'Candidate', retired: 'Retired' }

const edgeStyle: Record<string, { stroke: string; dashed?: boolean }> = {
  supersedes: { stroke: color.violet },
  contradicts: { stroke: color.red, dashed: true },
  reaffirms: { stroke: color.green },
  refines: { stroke: color.turq },
}

export function BeliefGraph({ graph, selected, onSelect }: {
  graph: Graph
  selected: string | null
  onSelect: (id: string) => void
}) {
  const nodes: Node[] = useMemo(() => {
    // pack each status into its own column, ordered top→bottom by capture date
    const rowOf = new Map<string, number>()
    const byStatus: Record<string, typeof graph.nodes> = {}
    graph.nodes.forEach((n) => ((byStatus[n.status] ??= []).push(n)))
    Object.values(byStatus).forEach((list) => {
      list
        .sort((a, b) => a.valid_from.localeCompare(b.valid_from) || a.id.localeCompare(b.id))
        .forEach((n, i) => rowOf.set(n.id, i))
    })

    // column header labels (non-interactive)
    const headers: Node[] = Object.keys(STATUS_COL).map((s) => ({
      id: `__hdr_${s}`,
      position: { x: (STATUS_COL[s] ?? 0) * COL_X, y: -64 },
      draggable: false,
      selectable: false,
      data: { label: <div className={styles.colHead}>{COL_LABEL[s]}</div> },
      style: { width: 180, border: 'none', background: 'transparent', boxShadow: 'none', padding: 0 },
    }))

    const beliefNodes: Node[] = graph.nodes.map((b) => {
      const c = statusColor[b.status] ?? color.black40
      const isSel = selected === b.id
      const trustPct = Math.round((b.trust ?? 0) * 100)
      return {
        id: b.id,
        position: { x: (STATUS_COL[b.status] ?? 1) * COL_X, y: (rowOf.get(b.id) ?? 0) * ROW_Y },
        data: {
          label: (
            <div className={styles.card}>
              <div className={styles.cardTop}>
                <span className={styles.cardId}>{b.id}</span>
                <span className={styles.pill} style={{ color: c, borderColor: c, background: `${c}14` }}>
                  {b.status}
                </span>
              </div>
              <div className={styles.cardScope}>{b.scope}</div>
              <div className={styles.cardMeta}>
                <span className={styles.trustTrack}>
                  <span className={styles.trustFill} style={{ width: `${trustPct}%`, background: c }} />
                </span>
                <span className={styles.trustNum}>trust {trustPct}%</span>
              </div>
              {b.contribution_eur !== 0 && (
                <div className={styles.cardEur}>
                  {b.contribution_eur > 0 ? '+' : ''}€{Math.round(b.contribution_eur).toLocaleString()}
                </div>
              )}
            </div>
          ),
        },
        style: {
          width: 180,
          borderRadius: 8,
          border: `${isSel ? 2 : 1}px solid ${isSel ? color.violet : c}`,
          background: color.white,
          boxShadow: isSel ? '0 0 0 3px rgba(95,38,224,0.15)' : '0 1px 3px rgba(0,0,0,0.06)',
          opacity: b.status === 'retired' ? 0.85 : 1,
          padding: 0,
        },
      }
    })
    return [...headers, ...beliefNodes]
  }, [graph, selected])

  const edges: Edge[] = useMemo(
    () =>
      graph.edges.map((e, i) => {
        const s = edgeStyle[e.kind] ?? { stroke: color.black40 }
        return {
          id: `e${i}`,
          source: e.src,
          target: e.dst,
          type: 'smoothstep',
          label: e.kind,
          labelStyle: { fontSize: 10, fill: s.stroke, fontWeight: 500 },
          labelBgStyle: { fill: color.white, fillOpacity: 0.9 },
          labelBgPadding: [4, 2] as [number, number],
          animated: e.kind === 'supersedes',
          style: { stroke: s.stroke, strokeDasharray: s.dashed ? '5 4' : undefined, strokeWidth: 1.6 },
          markerEnd: { type: MarkerType.ArrowClosed, color: s.stroke, width: 16, height: 16 },
        }
      }),
    [graph],
  )

  return (
    <div className={styles.canvas}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        minZoom={0.2}
        nodesDraggable={false}
        nodesConnectable={false}
        onNodeClick={(_e, n) => {
          if (!n.id.startsWith('__hdr')) onSelect(n.id)
        }}
        proOptions={{ hideAttribution: true }}
      >
        <Background color={color.black20} gap={22} />
        <Controls showInteractive={false} />
      </ReactFlow>
      <div className={styles.legend}>
        <span className={styles.legendTitle}>arrows:</span>
        <span><i style={{ background: color.violet }} /> supersedes</span>
        <span><i style={{ background: color.red }} /> contradicts</span>
        <span><i style={{ background: color.green }} /> reaffirms</span>
        <span className={styles.sep} />
        <span className="caption">click a note for the full story</span>
      </div>
    </div>
  )
}
