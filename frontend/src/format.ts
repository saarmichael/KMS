// Turns raw numbers from the API into short text for the screen.

export function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`
  }
  if (bytes < 1024 * 1024) {
    return `${Math.round(bytes / 1024)} KB`
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function formatAge(isoTime: string): string {
  const seconds = (Date.now() - new Date(isoTime).getTime()) / 1000
  if (seconds < 60) {
    return 'just now'
  }
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) {
    return `${minutes} min ago`
  }
  const hours = Math.floor(minutes / 60)
  if (hours < 24) {
    return `${hours} h ago`
  }
  const days = Math.floor(hours / 24)
  if (days < 7) {
    return days === 1 ? '1 day ago' : `${days} days ago`
  }
  return new Date(isoTime).toLocaleDateString()
}
