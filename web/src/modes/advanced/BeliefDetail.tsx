import { X } from 'lucide-react'
import { useBelief } from '../../api/hooks'
import { StatusBadge } from '../../components/Badge'
import { euro } from '../../lib/format'
import { Loader } from '../../components/Loader'
import styles from './BeliefDetail.module.css'

// Right-hand drawer: full record for the selected belief node.
export function BeliefDetail({ id, onClose }: { id: string | null; onClose: () => void }) {
  const { data: b, isLoading } = useBelief(id)
  if (!id) return null
  return (
    <aside className={styles.drawer}>
      <div className={styles.head}>
        <span className={styles.id}>{id}</span>
        <button className={styles.close} onClick={onClose} aria-label="Close">
          <X size={16} strokeWidth={1.5} />
        </button>
      </div>
      {isLoading && <Loader label="Loading…" />}
      {b && (
        <div className={styles.body}>
          <div className={styles.row}>
            <StatusBadge status={b.status} />
            <span className={styles.kind}>{b.kind}</span>
          </div>
          <p className={styles.note}>{b.note}</p>

          <Field label="€ contribution">
            <b className={b.contribution_eur > 0 ? styles.pos : b.contribution_eur < 0 ? styles.neg : ''}>
              {euro(b.contribution_eur)}
            </b>
            <span className="caption"> (cost avoided vs. removing it)</span>
          </Field>
          <Field label="Scope">{b.scope}</Field>
          <Field label="Author">{b.author ?? '—'}</Field>
          <Field label="Trust">{b.trust.toFixed(2)}</Field>
          <Field label="Valid">
            {b.valid_from} → {b.valid_to ?? 'open'}
          </Field>
          <Field label="Evidence">
            <ul className={styles.evidence}>
              {b.evidence.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          </Field>
        </div>
      )}
    </aside>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className={styles.field}>
      <div className="overline">{label}</div>
      <div className={styles.value}>{children}</div>
    </div>
  )
}
