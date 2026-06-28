import { useNavigate } from 'react-router-dom'
import { Button } from '../components/Button'
import { SummaryBand } from '../components/SummaryBand'
import styles from './Landing.module.css'

// Overview: restrained cockpit intro. Gradient only on the headline accent + the AI CTA.
export function Landing() {
  const navigate = useNavigate()
  return (
    <div className={styles.wrap}>
      <section className={styles.hero}>
        <p className="overline">Compounding decisions · warehouse staffing</p>
        <h2 className={styles.title}>
          A staffing plan that <span className="gradient-text">learns every week</span>.
        </h2>
        <p className={styles.lede}>
          Helios watches the optimiser&apos;s error, curates what it learns into a living belief graph,
          and emits a cheaper, defensible plan — walk-forward, never reading the future.
        </p>
        <div className={styles.cta}>
          <Button onClick={() => navigate('/normal')}>Open planner&apos;s desk</Button>
          <Button variant="secondary" onClick={() => navigate('/advanced')}>
            Open knowledge cockpit
          </Button>
        </div>
      </section>

      <section className={styles.section}>
        <p className="overline">Results · 98 training days, walk-forward</p>
        <SummaryBand />
      </section>
    </div>
  )
}
