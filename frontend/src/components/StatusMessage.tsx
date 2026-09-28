// A centred block for empty, loading and error states: an icon, a heading, a line of help and an
// optional button.
import type { ReactNode } from 'react'

type StatusMessageProps = {
  icon: ReactNode
  title: string
  text?: string
  action?: ReactNode
}

export default function StatusMessage({ icon, title, text, action }: StatusMessageProps) {
  return (
    <div className="flex flex-col items-center px-6 py-20 text-center">
      <div className="text-text-subtle">{icon}</div>
      <h2 className="mt-4 text-base font-semibold text-text">{title}</h2>
      {text && <p className="mt-1 max-w-sm text-sm text-text-muted">{text}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}
