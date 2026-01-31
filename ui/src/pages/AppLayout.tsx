import { Outlet, Link, useLocation } from 'react-router-dom'
import { getPersistedUserId } from '@/lib/api'
import { useEffect, useState } from 'react'
import clsx from 'clsx'

// Icons as SVG components
const icons = {
  dashboard: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM14 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zM4 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1v-4zM14 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
    </svg>
  ),
  memories: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
    </svg>
  ),
  profile: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
    </svg>
  ),
  portfolio: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
    </svg>
  ),
  narrative: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
    </svg>
  ),
  intents: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
  settings: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  ),
  brain: (
    <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
    </svg>
  ),
}

const navItems = [
  { path: '/', label: 'Dashboard', icon: icons.dashboard },
  { path: '/memories', label: 'Memories', icon: icons.memories },
  { path: '/profile', label: 'Profile', icon: icons.profile },
  { path: '/portfolio', label: 'Portfolio', icon: icons.portfolio },
  { path: '/narrative', label: 'Narrative', icon: icons.narrative },
  { path: '/intents', label: 'Intents', icon: icons.intents },
]

const secondaryNavItems = [
  { path: '/settings', label: 'Settings', icon: icons.settings },
]

export function AppLayout() {
  const location = useLocation()
  const [userId, setUserId] = useState('')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  useEffect(() => { setUserId(getPersistedUserId()) }, [location])

  function onChangeUserId(e: React.ChangeEvent<HTMLInputElement>) {
    const v = e.target.value
    setUserId(v)
    const url = new URL(window.location.href)
    url.searchParams.set('user_id', v)
    localStorage.setItem('user_id', v)
    window.history.replaceState({}, '', url.toString())
  }

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/'
    return location.pathname.startsWith(path)
  }

  return (
    <div className="min-h-screen flex" style={{ background: 'var(--bg-primary)' }}>
      {/* Sidebar */}
      <aside className={clsx(
        'sidebar flex flex-col transition-all duration-200',
        sidebarCollapsed ? 'w-16' : 'w-56'
      )}>
        {/* Logo */}
        <div className="p-4 flex items-center gap-3">
          <div className="text-amber-500">
            {icons.brain}
          </div>
          {!sidebarCollapsed && (
            <div>
              <div className="font-semibold text-[var(--text-primary)]">Agentic</div>
              <div className="text-xs text-[var(--text-tertiary)]">Memories</div>
            </div>
          )}
        </div>

        {/* Main navigation */}
        <nav className="flex-1 px-3 py-2 space-y-1">
          {navItems.map(item => (
            <Link
              key={item.path}
              to={item.path}
              className={clsx(
                'sidebar-item',
                isActive(item.path) && 'active'
              )}
              title={sidebarCollapsed ? item.label : undefined}
            >
              {item.icon}
              {!sidebarCollapsed && <span>{item.label}</span>}
            </Link>
          ))}
        </nav>

        {/* Secondary navigation */}
        <div className="px-3 py-2 border-t" style={{ borderColor: 'var(--border-primary)' }}>
          {secondaryNavItems.map(item => (
            <Link
              key={item.path}
              to={item.path}
              className={clsx(
                'sidebar-item',
                isActive(item.path) && 'active'
              )}
              title={sidebarCollapsed ? item.label : undefined}
            >
              {item.icon}
              {!sidebarCollapsed && <span>{item.label}</span>}
            </Link>
          ))}
        </div>

        {/* Collapse toggle */}
        <button
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          className="p-3 text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors"
        >
          <svg className={clsx('w-5 h-5 transition-transform', sidebarCollapsed && 'rotate-180')} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          </svg>
        </button>
      </aside>

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-h-screen overflow-hidden">
        {/* Top bar */}
        <header className="h-14 flex items-center justify-between px-6" style={{
          background: 'var(--bg-secondary)',
          borderBottom: '1px solid var(--border-primary)'
        }}>
          <div className="flex items-center gap-4">
            <h1 className="text-lg font-medium text-[var(--text-primary)]">
              {navItems.find(i => isActive(i.path))?.label ||
               secondaryNavItems.find(i => isActive(i.path))?.label ||
               'Dashboard'}
            </h1>
          </div>

          <div className="flex items-center gap-4">
            {/* User ID input */}
            <div className="flex items-center gap-2">
              <label className="text-sm text-[var(--text-tertiary)]">User ID</label>
              <input
                className="rounded-lg px-3 py-1.5 text-sm w-40"
                value={userId}
                onChange={onChangeUserId}
                placeholder="Enter user ID..."
              />
            </div>

            {/* Status indicator */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg" style={{ background: 'var(--bg-tertiary)' }}>
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs text-[var(--text-secondary)]">Connected</span>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto p-6">
          <div className="max-w-7xl mx-auto animate-fade-in">
            <Outlet />
          </div>
        </main>
      </div>

    </div>
  )
}
