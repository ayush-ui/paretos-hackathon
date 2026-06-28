import type { BeliefNode, BeliefStatus } from '../../api/types'
import { euro } from '../../lib/format'
import styles from './BeliefList.module.css'

const GROUPS: { status: BeliefStatus; title: string; blurb: string }[] = [
  { status: 'active', title: 'Active', blurb: 'Trusted — these notes are currently shaping the plan.' },
  { status: 'candidate', title: 'Candidate', blurb: 'Still being tested against incoming data.' },
  { status: 'retired', title: 'Retired', blurb: 'Proved wrong or stale — discarded, kept for the record.' },
]

// Readable list of the planner notes, grouped by lifecycle. The legible heart of the Advanced view.
export function BeliefList({ nodes, onOpen }: { nodes: BeliefNode[]; onOpen: (id: string) => void }) {
  return (
    <div className={styles.wrap}>
      {GROUPS.map((g) => {
        const items = nodes.filter((n) => n.status === g.status)
        if (!items.length) return null
        return (
          <section key={g.status}>
            <div className={styles.groupHead}>
              <span className={`${styles.dot} ${styles[g.status]}`} />
              <h5>{g.title}</h5>
              <span className={styles.count}>{items.length}</span>
              <span className="caption">{g.blurb}</span>
            </div>
            <div className={styles.grid}>
              {items.map((b) => (
                <button key={b.id} className={styles.card} onClick={() => onOpen(b.id)}>
                  <div className={styles.cardTop}>
                    <span className={styles.scope}>{b.scope}</span>
                    <span className={styles.author}>{b.author ?? '—'}</span>
                  </div>
                  <p className={styles.note}>{b.note}</p>
                  <div className={styles.cardFoot}>
                    <span className={styles.id}>{b.id}</span>
                    {b.contribution_eur !== 0 && (
                      <span className={b.contribution_eur > 0 ? styles.worth : styles.cost}>
                        worth {euro(b.contribution_eur)}
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </section>
        )
      })}
    </div>
  )
}
