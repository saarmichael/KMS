// The MSW service worker, answering /api/... in the browser from handlers.ts (F1).
import { setupWorker } from 'msw/browser'
import { handlers } from './handlers'

export const worker = setupWorker(...handlers)
