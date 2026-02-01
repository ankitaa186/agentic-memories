import { useQuery } from '@tanstack/react-query'
import { apiGet, getPersistedUserId } from '@/lib/api'
import { useEffect, useState } from 'react'
import clsx from 'clsx'

type ProfileData = {
  user_id: string
  profile: Record<string, Record<string, unknown>>
  completeness_pct: number
  populated_fields: number
  total_fields: number
  last_updated?: string
}

type CompletenessData = {
  user_id: string
  overall_completeness_pct: number
  populated_fields: number
  total_fields: number
  categories: Record<string, {
    completeness_pct: number
    populated: number
    total: number
    missing: string[]
  }>
  high_value_gaps: string[]
}

const categoryIcons: Record<string, string> = {
  basics: '👤',
  preferences: '⚙️',
  goals: '🎯',
  interests: '💡',
  background: '📚',
  health: '❤️',
  personality: '🧠',
  values: '⭐',
}

const categoryColors: Record<string, string> = {
  basics: 'from-blue-500 to-blue-600',
  preferences: 'from-purple-500 to-purple-600',
  goals: 'from-amber-500 to-amber-600',
  interests: 'from-emerald-500 to-emerald-600',
  background: 'from-cyan-500 to-cyan-600',
  health: 'from-red-500 to-red-600',
  personality: 'from-pink-500 to-pink-600',
  values: 'from-orange-500 to-orange-600',
}

// Helper to extract and format profile field values
function formatProfileValue(value: unknown): string {
  if (value === null || value === undefined) return '—'

  // Handle {value: ..., last_updated: ...} format
  if (typeof value === 'object' && value !== null && 'value' in value) {
    const innerValue = (value as { value: unknown }).value
    return formatProfileValue(innerValue)
  }

  // Handle arrays
  if (Array.isArray(value)) {
    return value.map(item => {
      if (typeof item === 'object' && item !== null) {
        // For objects in arrays, show key details
        const entries = Object.entries(item)
          .filter(([k]) => k !== 'last_updated')
          .map(([k, v]) => `${k}: ${v}`)
        return entries.join(', ')
      }
      return String(item)
    }).join('; ')
  }

  // Handle nested objects (like spouse: {name: "...", nickname: "..."})
  if (typeof value === 'object' && value !== null) {
    const entries = Object.entries(value)
      .filter(([k]) => k !== 'last_updated')
      .map(([k, v]) => `${k}: ${v}`)
    return entries.join(', ')
  }

  return String(value)
}

export function Profile() {
  const [userId, setUserId] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  useEffect(() => { setUserId(getPersistedUserId()) }, [])

  const { data: profile, isLoading } = useQuery({
    queryKey: ['profile', userId],
    queryFn: () => apiGet<ProfileData>(`/v1/profile?user_id=${userId}`),
    enabled: !!userId,
  })

  const { data: completeness } = useQuery({
    queryKey: ['completeness', userId],
    queryFn: () => apiGet<CompletenessData>(`/v1/profile/completeness?user_id=${userId}&detailed=true`),
    enabled: !!userId,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-amber-500 border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-[var(--text-primary)]">Profile</h2>
          <p className="text-[var(--text-secondary)]">View and manage your identity</p>
        </div>
        {profile?.last_updated && (
          <div className="text-sm text-[var(--text-tertiary)]">
            Last updated: {new Date(profile.last_updated).toLocaleDateString()}
          </div>
        )}
      </div>

      {/* Completeness Overview */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium text-[var(--text-primary)]">Profile Completeness</h3>
          <div className="text-2xl font-bold text-amber-500">
            {profile?.completeness_pct?.toFixed(0) || 0}%
          </div>
        </div>
        <div className="h-3 rounded-full mb-4" style={{ background: 'var(--bg-tertiary)' }}>
          <div
            className="h-full rounded-full bg-gradient-to-r from-amber-500 to-orange-500 transition-all"
            style={{ width: `${profile?.completeness_pct || 0}%` }}
          />
        </div>
        <div className="flex items-center gap-4 text-sm text-[var(--text-secondary)]">
          <span>{profile?.populated_fields || 0} of {profile?.total_fields || 0} fields populated</span>
        </div>

        {/* High value gaps */}
        {completeness?.high_value_gaps && completeness.high_value_gaps.length > 0 && (
          <div className="mt-4 p-3 rounded-lg" style={{ background: 'var(--accent-muted)' }}>
            <div className="text-sm font-medium text-amber-400 mb-2">Suggested to complete:</div>
            <div className="flex flex-wrap gap-2">
              {completeness.high_value_gaps.map((gap, i) => (
                <span key={i} className="badge badge-amber">{gap}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Category Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {completeness?.categories && Object.entries(completeness.categories).map(([category, data]) => (
          <button
            key={category}
            onClick={() => setSelectedCategory(selectedCategory === category ? null : category)}
            className={clsx(
              'card p-4 text-left transition-all hover:scale-[1.02]',
              selectedCategory === category && 'ring-2 ring-amber-500'
            )}
          >
            <div className="flex items-center gap-3 mb-3">
              <div className={clsx(
                'w-10 h-10 rounded-lg flex items-center justify-center text-xl bg-gradient-to-br',
                categoryColors[category] || 'from-gray-500 to-gray-600'
              )}>
                {categoryIcons[category] || '📁'}
              </div>
              <div>
                <div className="font-medium text-[var(--text-primary)] capitalize">{category}</div>
                <div className="text-xs text-[var(--text-tertiary)]">{data.populated}/{data.total} fields</div>
              </div>
            </div>
            <div className="h-1.5 rounded-full" style={{ background: 'var(--bg-tertiary)' }}>
              <div
                className={clsx('h-full rounded-full bg-gradient-to-r', categoryColors[category] || 'from-gray-500 to-gray-600')}
                style={{ width: `${data.completeness_pct}%` }}
              />
            </div>
            <div className="text-xs text-[var(--text-tertiary)] mt-2">
              {data.completeness_pct.toFixed(0)}% complete
            </div>
          </button>
        ))}
      </div>

      {/* Selected Category Details */}
      {selectedCategory && profile?.profile?.[selectedCategory] && (
        <div className="card p-6 animate-fade-in">
          <div className="flex items-center gap-3 mb-4">
            <div className={clsx(
              'w-10 h-10 rounded-lg flex items-center justify-center text-xl bg-gradient-to-br',
              categoryColors[selectedCategory] || 'from-gray-500 to-gray-600'
            )}>
              {categoryIcons[selectedCategory] || '📁'}
            </div>
            <div>
              <h3 className="text-lg font-medium text-[var(--text-primary)] capitalize">{selectedCategory}</h3>
              <p className="text-sm text-[var(--text-secondary)]">
                {completeness?.categories?.[selectedCategory]?.populated || 0} fields populated
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(profile.profile[selectedCategory]).map(([field, value]) => (
              <div
                key={field}
                className="p-4 rounded-lg"
                style={{ background: 'var(--bg-tertiary)' }}
              >
                <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wide mb-1">
                  {field.replace(/_/g, ' ')}
                </div>
                <div className="text-[var(--text-primary)] break-words">
                  {formatProfileValue(value)}
                </div>
              </div>
            ))}
          </div>

          {/* Missing fields */}
          {completeness?.categories?.[selectedCategory]?.missing && completeness.categories[selectedCategory].missing.length > 0 && (
            <div className="mt-4">
              <div className="text-sm text-[var(--text-tertiary)] mb-2">Missing fields:</div>
              <div className="flex flex-wrap gap-2">
                {completeness.categories[selectedCategory].missing.map((field, i) => (
                  <span key={i} className="badge badge-neutral">{field.replace(/_/g, ' ')}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* All Profile Data */}
      {!selectedCategory && profile?.profile && (
        <div className="card p-6">
          <h3 className="text-lg font-medium text-[var(--text-primary)] mb-4">All Profile Data</h3>
          <div className="space-y-6">
            {Object.entries(profile.profile).map(([category, fields]) => (
              <div key={category}>
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xl">{categoryIcons[category] || '📁'}</span>
                  <h4 className="font-medium text-[var(--text-primary)] capitalize">{category}</h4>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {Object.entries(fields || {}).map(([field, value]) => (
                    <div
                      key={field}
                      className="p-3 rounded-lg"
                      style={{ background: 'var(--bg-tertiary)' }}
                    >
                      <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wide">
                        {field.replace(/_/g, ' ')}
                      </div>
                      <div className="text-sm text-[var(--text-primary)] mt-1 break-words">
                        {formatProfileValue(value)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
