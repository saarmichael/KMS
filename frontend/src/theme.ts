// Light or dark. The theme lives in one place, the `data-theme` attribute on <html>: the script in index.html
// sets it before the first paint, and the toggle changes it. The colours follow from index.css.

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'sift-theme'

// The browser bar's colour on phones, matching each theme's page background.
const THEME_COLORS: Record<Theme, string> = {
  light: '#F8F4EB',
  dark: '#0E151C',
}

// The theme on the page now, as the script in index.html left it.
export function currentTheme(): Theme {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
}

// Switches the page to `theme` and remembers the choice for the next visit.
export function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', THEME_COLORS[theme])
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    // Storage can be blocked; the theme still changes for this page.
  }
}
