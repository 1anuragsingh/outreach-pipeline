import { NavLink } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/',         label: 'Pipeline', end: true },
  { to: '/contacts', label: 'Contacts' },
  { to: '/emails',   label: 'Emails' },
]

function navClass({ isActive }) {
  return [
    'flex items-center px-4 py-2.5 text-sm rounded-r transition-colors',
    isActive
      ? 'text-white font-semibold border-l-2 border-blue-400 bg-white/10 pl-3.5'
      : 'text-gray-400 hover:text-white hover:bg-white/5 border-l-2 border-transparent pl-3.5',
  ].join(' ')
}

export default function Sidebar() {
  return (
    <aside className="w-[200px] flex-shrink-0 bg-gray-900 flex flex-col h-full">

      {/* Logo */}
      <div className="px-5 py-5 border-b border-white/10">
        <span className="text-white font-bold text-base tracking-tight">
          OutreachAI
        </span>
      </div>

      {/* Main nav */}
      <nav className="flex-1 py-3 flex flex-col gap-0.5">
        {NAV_ITEMS.map(({ to, label, end }) => (
          <NavLink key={to} to={to} end={end} className={navClass}>
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Settings pinned to bottom */}
      <div className="border-t border-white/10 py-3">
        <NavLink to="/settings" className={navClass}>
          Settings
        </NavLink>
      </div>

    </aside>
  )
}
