// A round button in the top bar's corner that switches between the light and the dark theme. It shows
// where it leads: a moon in the light theme, a sun in the dark one.
import type { Theme } from '../theme'
import { MoonIcon, SunIcon } from './icons'

type ThemeToggleProps = {
  theme: Theme
  onToggle: () => void
}

export default function ThemeToggle({ theme, onToggle }: ThemeToggleProps) {
  const label = theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme'
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={label}
      title={label}
      className="rounded-full p-2 text-text-muted hover:bg-surface-hover hover:text-text"
    >
      {theme === 'light' ? <MoonIcon className="size-5" /> : <SunIcon className="size-5" />}
    </button>
  )
}
