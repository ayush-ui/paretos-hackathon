import { useEffect, useMemo, useState } from 'react'
import { useGraph, useCompounding } from '../../api/hooks'
import { BeliefGraph } from './BeliefGraph'
import { ProvenanceGraph } from './ProvenanceGraph'
import { BeliefList } from './BeliefList'
import { BeliefDetail } from './BeliefDetail'
import { KnowledgeIntro } from './KnowledgeIntro'
import { NoteComposer } from '../../components/NoteComposer'
import { TimeSlider } from './TimeSlider'
import { DecisionTrace } from './DecisionTrace'
import { CompoundingTimeline } from './CompoundingTimeline'
import { SyntheticPanel } from './SyntheticPanel'
import { StaffingPanel } from './StaffingPanel'
import { PanelLoader } from '../../components/Loader'
import styles from './KnowledgeCockpit.module.css'

type Tab = 'knowledge' | 'staffing' | 'trace' | 'compounding' | 'robustness'
const TABS: { key: Tab; label: string }[] = [
  { key: 'knowledge', label: 'Knowledge graph' },
  { key: 'staffing', label: 'Staffing' },
  { key: 'compounding', label: 'Compounding' },
  { key: 'trace', label: 'Decision trace' },
  { key: 'robustness', label: 'Robustness' },
]

type GraphMode = 'belief' | 'provenance'

export function KnowledgeCockpit() {
  const [tab, setTab] = useState<Tab>('knowledge')
  const [graphMode, setGraphMode] = useState<GraphMode>('belief')
  const { data: compounding } = useCompounding()
  const dates = useMemo(() => (compounding ?? []).map((p) => p.decision_date), [compounding])
  const [sliderIdx, setSliderIdx] = useState(-1) // -1 = uninitialised
  const [selected, setSelected] = useState<string | null>(null)

  // default the slider to the end (full curated graph) once the dates load
  useEffect(() => {
    if (dates.length && sliderIdx === -1) setSliderIdx(dates.length)
  }, [dates.length, sliderIdx])

  // slider at the last position (== dates.length) means "now / end state" → as_of null
  const asOf = sliderIdx >= 0 && sliderIdx < dates.length ? dates[sliderIdx] : null
  const { data: graph, isLoading: graphLoading } = useGraph(asOf)

  return (
    <div className={styles.wrap}>
      <header>
        <h3>Knowledge cockpit</h3>
        <p className="caption">
          The knowledge that governs the plan — what&apos;s active, retired, what it&apos;s worth, and why.
        </p>
      </header>

      <KnowledgeIntro />

      <nav className={styles.tabs}>
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`${styles.tab} ${tab === t.key ? styles.tabActive : ''}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {tab === 'knowledge' && (
        <div className={styles.graphLayout}>
          <div className={styles.graphMain}>
            <NoteComposer />

            <div className={styles.graphHeader}>
              <p className={styles.framing}>
                {graphMode === 'belief' ? (
                  <>
                    Each box is a planner note (a belief). The three columns are its lifecycle —{' '}
                    <b>active</b>, <b>candidate</b>, <b>retired</b> — and within a column, time runs top →
                    bottom. Arrows show how one note <b>supersedes</b>, <b>contradicts</b> or{' '}
                    <b>reaffirms</b> another.
                  </>
                ) : (
                  <>
                    The full audit trail: <b>sources</b> → <b>beliefs</b> → the weekly <b>decisions</b>{' '}
                    they shaped → the € <b>outcomes</b> reality delivered. Toggle link types below and{' '}
                    <b>click any node</b> to focus just its chain.
                  </>
                )}
              </p>
              <div className={styles.modeToggle} role="tablist" aria-label="Graph view">
                <button
                  className={`${styles.modeBtn} ${graphMode === 'belief' ? styles.modeOn : ''}`}
                  onClick={() => setGraphMode('belief')}
                >
                  Belief graph
                </button>
                <button
                  className={`${styles.modeBtn} ${graphMode === 'provenance' ? styles.modeOn : ''}`}
                  onClick={() => setGraphMode('provenance')}
                >
                  Provenance (advanced)
                </button>
              </div>
            </div>

            {dates.length > 0 && (
              <TimeSlider dates={dates} index={sliderIdx} onChange={setSliderIdx} />
            )}

            {graphMode === 'provenance' ? (
              <ProvenanceGraph asOf={asOf} onSelectBelief={setSelected} />
            ) : graph && !graphLoading ? (
              <>
                <BeliefGraph graph={graph} selected={selected} onSelect={setSelected} />
                <BeliefList nodes={graph.nodes} onOpen={setSelected} />
              </>
            ) : (
              <PanelLoader label="Loading the knowledge graph…" />
            )}
          </div>
          {selected && <BeliefDetail id={selected} onClose={() => setSelected(null)} />}
        </div>
      )}

      {tab === 'staffing' && <StaffingPanel />}
      {tab === 'compounding' && <CompoundingTimeline />}
      {tab === 'trace' && <DecisionTrace />}
      {tab === 'robustness' && <SyntheticPanel />}
    </div>
  )
}
