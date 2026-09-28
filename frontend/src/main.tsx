import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Poppins, the typeface of the Sift wordmark, bundled with the app rather than fetched from Google.
import '@fontsource/poppins/400.css'
import '@fontsource/poppins/500.css'
import '@fontsource/poppins/600.css'
import '@fontsource/poppins/700.css'
import './index.css'
import App from './App.tsx'

// Only `npm run dev:mock` sets the flag. The dynamic import keeps MSW out of the production bundle.
async function startMocksIfEnabled() {
  if (import.meta.env.VITE_MOCK_API !== 'true') {
    return
  }
  const { worker } = await import('./mocks/browser')
  // Requests that are not /api (the app's own files) go to the network untouched.
  await worker.start({ onUnhandledRequest: 'bypass' })
}

startMocksIfEnabled().then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
})
