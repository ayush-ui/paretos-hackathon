import type { ButtonHTMLAttributes } from 'react'
import styles from './Button.module.css'

// 'paretos' = brand-gradient variant, reserved for AI actions (see DESIGN_SYSTEM §5).
type Variant = 'primary' | 'secondary' | 'ghost' | 'paretos'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  rounded?: boolean
}

export function Button({ variant = 'primary', rounded, className, ...rest }: Props) {
  return (
    <button
      className={`${styles.btn} ${styles[variant]} ${rounded ? styles.rounded : ''} ${className ?? ''}`}
      {...rest}
    />
  )
}
