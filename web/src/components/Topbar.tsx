import styles from './Topbar.module.css'
import logoUrl from '../assets/paretos-logo.svg'

// Fixed 60px full-bleed white bar, hairline bottom border. Logo = official paretos brand mark.
export function Topbar() {
  return (
    <header className={styles.topbar}>
      <div className={styles.brand}>
        <img className={styles.mark} src={logoUrl} alt="paretos" />
        <span className={styles.wordmark}>paretos</span>
        <span className={styles.divider} />
        <span className={styles.product}>Helios staffing cockpit</span>
      </div>
    </header>
  )
}
