import { useState } from 'react'
import { Info, X, CheckCircle2, CircleDashed, XCircle } from 'lucide-react'
import { color } from '../../theme/theme'
import styles from './KnowledgeIntro.module.css'

// Plain-language framing so the Advanced view is understandable, not cryptic.
export function KnowledgeIntro() {
  const [open, setOpen] = useState(true)
  if (!open)
    return (
      <button className={styles.reopen} onClick={() => setOpen(true)}>
        <Info size={16} strokeWidth={1} /> What am I looking at?
      </button>
    )
  return (
    <div className={styles.panel}>
      <button className={styles.close} onClick={() => setOpen(false)} aria-label="Dismiss">
        <X size={16} strokeWidth={1} />
      </button>
      <p className="overline">What am I looking at?</p>
      <p className={styles.body}>
        Every item below is a <b>note a warehouse planner wrote</b> — a real observation like
        &ldquo;picking is over-staffed&rdquo; or &ldquo;heat is killing throughput.&rdquo; The engine
        treats each note as a claim and <b>tests it against what actually happened</b>, week by week.
        That&apos;s the knowledge that quietly adjusts the staffing plan — and this is your master view of it.
      </p>
      <div className={styles.statuses}>
        <span><CheckCircle2 size={15} strokeWidth={1.5} color={color.violet} /> <b>Active</b> — trusted, currently shaping the plan</span>
        <span><CircleDashed size={15} strokeWidth={1.5} color={color.turq} /> <b>Candidate</b> — still being tested against new data</span>
        <span><XCircle size={15} strokeWidth={1.5} color={color.black40} /> <b>Retired</b> — proved wrong or stale, discarded</span>
      </div>
    </div>
  )
}
