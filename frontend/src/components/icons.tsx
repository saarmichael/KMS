// Outline icons from Heroicons (MIT licence, heroicons.com), copied as inline SVG paths.
// Each icon takes its size and colour from the `className` it is given, e.g. "size-5 text-gray-400".

type IconProps = { className?: string }

function OutlineIcon({ className, path }: IconProps & { path: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
      aria-hidden="true"
      className={className}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d={path} />
    </svg>
  )
}

export function StackIcon({ className }: IconProps) {
  return (
    <OutlineIcon
      className={className}
      path="M6.429 9.75 2.25 12l4.179 2.25m0-4.5 5.571 3 5.571-3m-11.142 0L2.25 7.5 12 2.25l9.75 5.25-4.179 2.25m0 0L21.75 12l-4.179 2.25m0 0 4.179 2.25L12 21.75 2.25 16.5l4.179-2.25m11.142 0-5.571 3-5.571-3"
    />
  )
}

export function FolderIcon({ className }: IconProps) {
  return (
    <OutlineIcon
      className={className}
      path="M2.25 12.75V12A2.25 2.25 0 0 1 4.5 9.75h15A2.25 2.25 0 0 1 21.75 12v.75m-8.69-6.44-2.12-2.12a1.5 1.5 0 0 0-1.061-.44H4.5A2.25 2.25 0 0 0 2.25 6v12a2.25 2.25 0 0 0 2.25 2.25h15A2.25 2.25 0 0 0 21.75 18V9a2.25 2.25 0 0 0-2.25-2.25h-5.379a1.5 1.5 0 0 1-1.06-.44Z"
    />
  )
}

export function ChevronDownIcon({ className }: IconProps) {
  return <OutlineIcon className={className} path="m19.5 8.25-7.5 7.5-7.5-7.5" />
}

export function CheckIcon({ className }: IconProps) {
  return <OutlineIcon className={className} path="m4.5 12.75 6 6 9-13.5" />
}

export function PlusIcon({ className }: IconProps) {
  return <OutlineIcon className={className} path="M12 4.5v15m7.5-7.5h-15" />
}

export function TrashIcon({ className }: IconProps) {
  return (
    <OutlineIcon
      className={className}
      path="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"
    />
  )
}

export function ExclamationIcon({ className }: IconProps) {
  return (
    <OutlineIcon
      className={className}
      path="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
    />
  )
}

export function UploadIcon({ className }: IconProps) {
  return (
    <OutlineIcon
      className={className}
      path="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5"
    />
  )
}

export function DocumentIcon({ className }: IconProps) {
  return (
    <OutlineIcon
      className={className}
      path="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
    />
  )
}

export function RetryIcon({ className }: IconProps) {
  return (
    <OutlineIcon
      className={className}
      path="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99"
    />
  )
}

export function AdjustmentsIcon({ className }: IconProps) {
  return (
    <OutlineIcon
      className={className}
      path="M10.5 6h9.75M10.5 6a1.5 1.5 0 1 1-3 0m3 0a1.5 1.5 0 1 0-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-9.75 0h9.75"
    />
  )
}

export function CloseIcon({ className }: IconProps) {
  return <OutlineIcon className={className} path="M6 18 18 6M6 6l12 12" />
}

export function SearchIcon({ className }: IconProps) {
  return (
    <OutlineIcon
      className={className}
      path="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z"
    />
  )
}

export function ArrowLeftIcon({ className }: IconProps) {
  return <OutlineIcon className={className} path="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
}

export function ExternalLinkIcon({ className }: IconProps) {
  return (
    <OutlineIcon
      className={className}
      path="M13.5 6H5.25A2.25 2.25 0 0 0 3 8.25v10.5A2.25 2.25 0 0 0 5.25 21h10.5A2.25 2.25 0 0 0 18 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"
    />
  )
}

export function DownloadIcon({ className }: IconProps) {
  return (
    <OutlineIcon
      className={className}
      path="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"
    />
  )
}

// A ring with one bright quarter, turned by Tailwind's `animate-spin`.
export function SpinnerIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className={`animate-spin ${className ?? ''}`}>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" className="opacity-20" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  )
}
