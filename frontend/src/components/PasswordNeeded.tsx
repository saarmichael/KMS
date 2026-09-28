// Shown in place of the whole app when the server asks for a password the browser does not have.
// The browser's own prompt only comes back on a page load, so the one way forward is a reload.
import StatusMessage from './StatusMessage'
import { ExclamationIcon } from './icons'

export default function PasswordNeeded() {
  return (
    <div className="min-h-screen bg-gray-50">
      <StatusMessage
        icon={<ExclamationIcon className="size-12" />}
        title="Password needed"
        text="The app's password is needed. Reload the page and enter it in the browser's prompt."
        action={
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-xs hover:bg-indigo-500"
          >
            Reload
          </button>
        }
      />
    </div>
  )
}
