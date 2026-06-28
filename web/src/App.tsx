import { Outlet } from 'react-router-dom'
import { Topbar } from './components/Topbar'
import { Sidebar } from './components/Sidebar'
import styles from './App.module.css'

// Cockpit shell: fixed topbar + left sidebar; content scrolls with 40px gutters, full-width (no cap).
export function App() {
  return (
    <div className={styles.app}>
      <Topbar />
      <div className={styles.body}>
        <Sidebar />
        <main className={styles.content}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
