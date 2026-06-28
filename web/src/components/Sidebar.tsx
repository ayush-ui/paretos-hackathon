import { NavLink } from 'react-router-dom'
import { LayoutDashboard, ClipboardList, Share2 } from 'lucide-react'
import styles from './Sidebar.module.css'

// Fixed left rail, 180px, white, hairline right border. Selected item uses violet.
// Icons: Lucide at stroke-width 1 (flagged substitute for the in-house line set — DESIGN_SYSTEM §6).
const nav = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/normal', label: "Planner's desk", icon: ClipboardList, end: false },
  { to: '/advanced', label: 'Knowledge cockpit', icon: Share2, end: false },
]

export function Sidebar() {
  return (
    <nav className={styles.sidebar} aria-label="Primary">
      {nav.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) => `${styles.item} ${isActive ? styles.active : ''}`}
        >
          <Icon size={18} strokeWidth={1} className={styles.icon} />
          <span>{label}</span>
        </NavLink>
      ))}
    </nav>
  )
}
