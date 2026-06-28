import styles from './Topbar.module.css'

// Fixed 60px full-bleed white bar, hairline bottom border. Logo = 60x60 square w/ brand gradient.
export function Topbar() {
  return (
    <header className={styles.topbar}>
      <div className={styles.brand}>
        <div className={styles.mark} aria-hidden>
          <span className={styles.arch}>⌒</span>
        </div>
        <span className={styles.wordmark}>paretos</span>
        <span className={styles.divider} />
        <span className={styles.product}>Helios staffing cockpit</span>
      </div>
    </header>
  )
}
