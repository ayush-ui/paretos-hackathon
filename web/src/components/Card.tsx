import type { HTMLAttributes, ReactNode } from 'react'
import styles from './Card.module.css'

interface Props extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  title?: ReactNode
  tag?: ReactNode
  large?: boolean
  children: ReactNode
}

export function Card({ title, tag, large, children, className, ...rest }: Props) {
  return (
    <div className={`${styles.card} ${large ? styles.large : ''} ${className ?? ''}`} {...rest}>
      {(title || tag) && (
        <div className={styles.head}>
          {title && <h6>{title}</h6>}
          {tag && <div>{tag}</div>}
        </div>
      )}
      {children}
    </div>
  )
}
