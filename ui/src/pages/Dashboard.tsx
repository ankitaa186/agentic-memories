import { useQuery } from '@tanstack/react-query'
import { apiGet, getPersistedUserId } from '@/lib/api'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

type ProfileData = {
  user_id: string
  profile: Record<string, Record<string, unknown>>
  completeness_pct: number
  populated_fields: number
  total_fields: number
}

type PortfolioData = {
  user_id: string
  holdings: Array<{ ticker: string; shares: number; avg_price?: number }>
  total_holdings: number
}

type MemoriesData = {
  results: Array<{
    id: string
    content: string
    layer: string
    type: string
    metadata?: Record<string, unknown>
  }>
}

export function Dashboard() {
  const [userId, setUserId] = useState('')
  useEffect(() => { setUserId(getPersistedUserId()) }, [])

  const { data: profile } = useQuery({
    queryKey: ['profile', userId],
    queryFn: () => apiGet<ProfileData>(`/v1/profile?user_id=${userId}`),
    enabled: !!userId,
  })

  const { data: portfolio } = useQuery({
    queryKey: ['portfolio', userId],
    queryFn: () => apiGet<PortfolioData>(`/v1/portfolio?user_id=${userId}`),
    enabled: !!userId,
  })

  const { data: memories } = useQuery({
    queryKey: ['memories-recent', userId],
    queryFn: () => apiGet<MemoriesData>(`/v1/retrieve?user_id=${userId}&limit=5&sort=newest`),
    enabled: !!userId,
  })

  const memoriesCount = memories?.results?.length || 0

  return (
    <div className="space-y-6">
      {/* Welcome Section */}
      <div className="card p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-[var(--text-primary)]">
              Welcome back{(() => {
                const basics = profile?.profile?.basics
                if (!basics) return ''
                // Handle name as string or object with value property
                const name = basics.name
                if (typeof name === 'string') return `, ${name}`
                if (name && typeof name === 'object' && 'value' in name) return `, ${(name as {value: string}).value}`
                return ''
              })()}
            </h2>
            <p className="text-[var(--text-secondary)] mt-1">
              Here's an overview of your memory system
            </p>
          </div>
          <div className="text-6xl">🧠</div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="stat-card">
          <div className="stat-value text-amber-500">{memoriesCount}</div>
          <div className="stat-label">Recent Memories</div>
        </div>
        <div className="stat-card">
          <div className="stat-value text-blue-500">{profile?.completeness_pct?.toFixed(0) || 0}%</div>
          <div className="stat-label">Profile Complete</div>
        </div>
        <div className="stat-card">
          <div className="stat-value text-emerald-500">{portfolio?.total_holdings || 0}</div>
          <div className="stat-label">Holdings</div>
        </div>
        <div className="stat-card">
          <div className="stat-value text-purple-500">{profile?.populated_fields || 0}</div>
          <div className="stat-label">Profile Fields</div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Memories */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-[var(--text-primary)]">Recent Memories</h3>
            <Link to="/memories" className="text-sm text-amber-500 hover:text-amber-400">
              View all →
            </Link>
          </div>
          <div className="space-y-3">
            {memories?.results && Array.isArray(memories.results) && memories.results.length > 0 ? (
              memories.results.slice(0, 5).map((memory) => (
                <div
                  key={memory.id}
                  className="p-3 rounded-lg transition-colors"
                  style={{ background: 'var(--bg-tertiary)' }}
                >
                  <p className="text-sm text-[var(--text-primary)] line-clamp-2">{memory.content}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <span className={`badge ${memory.layer === 'semantic' ? 'badge-blue' : memory.layer === 'short-term' ? 'badge-amber' : 'badge-purple'}`}>
                      {memory.layer}
                    </span>
                    <span className="text-xs text-[var(--text-tertiary)]">
                      {memory.metadata?.timestamp ? new Date(memory.metadata.timestamp as string).toLocaleDateString() : ''}
                    </span>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center py-8 text-[var(--text-tertiary)]">
                <div className="text-3xl mb-2">💭</div>
                <p>No memories yet</p>
              </div>
            )}
          </div>
        </div>

        {/* Profile Overview */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-[var(--text-primary)]">Profile Overview</h3>
            <Link to="/profile" className="text-sm text-amber-500 hover:text-amber-400">
              Edit profile →
            </Link>
          </div>

          {/* Completeness bar */}
          <div className="mb-4">
            <div className="flex items-center justify-between text-sm mb-1">
              <span className="text-[var(--text-secondary)]">Completeness</span>
              <span className="text-[var(--text-primary)] font-medium">{profile?.completeness_pct?.toFixed(0) || 0}%</span>
            </div>
            <div className="h-2 rounded-full" style={{ background: 'var(--bg-tertiary)' }}>
              <div
                className="h-full rounded-full bg-gradient-to-r from-amber-500 to-orange-500 transition-all"
                style={{ width: `${profile?.completeness_pct || 0}%` }}
              />
            </div>
          </div>

          {/* Profile categories */}
          <div className="grid grid-cols-2 gap-3">
            {profile?.profile && Object.entries(profile.profile).slice(0, 6).map(([category, fields]) => (
              <div
                key={category}
                className="p-3 rounded-lg"
                style={{ background: 'var(--bg-tertiary)' }}
              >
                <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wide mb-1">
                  {category}
                </div>
                <div className="text-sm text-[var(--text-primary)]">
                  {Object.keys(fields || {}).length} fields
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Portfolio Summary */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-[var(--text-primary)]">Portfolio</h3>
            <Link to="/portfolio" className="text-sm text-amber-500 hover:text-amber-400">
              View all →
            </Link>
          </div>
          {portfolio?.holdings && portfolio.holdings.length > 0 ? (
            <div className="space-y-2">
              {portfolio.holdings.slice(0, 5).map((holding, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between p-3 rounded-lg"
                  style={{ background: 'var(--bg-tertiary)' }}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center">
                      <span className="text-emerald-400 text-xs font-bold">{holding.ticker?.slice(0, 2)}</span>
                    </div>
                    <div>
                      <div className="text-sm font-medium text-[var(--text-primary)]">{holding.ticker}</div>
                      <div className="text-xs text-[var(--text-tertiary)]">{holding.shares} shares</div>
                    </div>
                  </div>
                  {holding.avg_price && (
                    <div className="text-sm text-[var(--text-secondary)]">
                      @${holding.avg_price.toFixed(2)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-[var(--text-tertiary)]">
              <div className="text-3xl mb-2">📊</div>
              <p>No holdings yet</p>
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div className="card p-5">
          <h3 className="text-lg font-medium text-[var(--text-primary)] mb-4">Quick Actions</h3>
          <div className="grid grid-cols-2 gap-3">
            <Link
              to="/memories"
              className="p-4 rounded-lg transition-all hover:scale-[1.02]"
              style={{ background: 'var(--bg-tertiary)' }}
            >
              <div className="text-2xl mb-2">🔍</div>
              <div className="text-sm font-medium text-[var(--text-primary)]">Search Memories</div>
              <div className="text-xs text-[var(--text-tertiary)]">Find past experiences</div>
            </Link>
            <Link
              to="/narrative"
              className="p-4 rounded-lg transition-all hover:scale-[1.02]"
              style={{ background: 'var(--bg-tertiary)' }}
            >
              <div className="text-2xl mb-2">📖</div>
              <div className="text-sm font-medium text-[var(--text-primary)]">Generate Narrative</div>
              <div className="text-xs text-[var(--text-tertiary)]">Create your story</div>
            </Link>
            <Link
              to="/profile"
              className="p-4 rounded-lg transition-all hover:scale-[1.02]"
              style={{ background: 'var(--bg-tertiary)' }}
            >
              <div className="text-2xl mb-2">👤</div>
              <div className="text-sm font-medium text-[var(--text-primary)]">Update Profile</div>
              <div className="text-xs text-[var(--text-tertiary)]">Edit your info</div>
            </Link>
            <Link
              to="/intents"
              className="p-4 rounded-lg transition-all hover:scale-[1.02]"
              style={{ background: 'var(--bg-tertiary)' }}
            >
              <div className="text-2xl mb-2">⏰</div>
              <div className="text-sm font-medium text-[var(--text-primary)]">Manage Intents</div>
              <div className="text-xs text-[var(--text-tertiary)]">Scheduled actions</div>
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
