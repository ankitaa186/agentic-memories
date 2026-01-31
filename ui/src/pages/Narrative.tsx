import { useQuery, useMutation } from '@tanstack/react-query'
import { apiGet, apiPost, getPersistedUserId } from '@/lib/api'
import { useEffect, useState } from 'react'

type NarrativeResponse = {
  user_id: string
  narrative: string
  sources_count: number
  time_range?: {
    start?: string
    end?: string
  }
  generated_at: string
}

export function Narrative() {
  const [userId, setUserId] = useState('')
  const [timeRange, setTimeRange] = useState('all')
  const [customStart, setCustomStart] = useState('')
  const [customEnd, setCustomEnd] = useState('')
  useEffect(() => { setUserId(getPersistedUserId()) }, [])

  const generateNarrative = useMutation({
    mutationFn: async () => {
      const params: Record<string, string> = { user_id: userId }
      if (timeRange === 'week') {
        const now = new Date()
        const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
        params.start_date = weekAgo.toISOString()
        params.end_date = now.toISOString()
      } else if (timeRange === 'month') {
        const now = new Date()
        const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
        params.start_date = monthAgo.toISOString()
        params.end_date = now.toISOString()
      } else if (timeRange === 'custom' && customStart) {
        params.start_date = new Date(customStart).toISOString()
        if (customEnd) {
          params.end_date = new Date(customEnd).toISOString()
        }
      }
      return apiPost<NarrativeResponse>('/v1/narrative', params)
    },
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-semibold text-[var(--text-primary)]">Narrative</h2>
        <p className="text-[var(--text-secondary)]">Generate your life story from memories</p>
      </div>

      {/* Controls */}
      <div className="card p-6">
        <h3 className="text-lg font-medium text-[var(--text-primary)] mb-4">Generate Narrative</h3>

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-[var(--text-secondary)] mb-2">Time Range</label>
            <div className="flex flex-wrap gap-2">
              {[
                { value: 'all', label: 'All Time' },
                { value: 'week', label: 'Last Week' },
                { value: 'month', label: 'Last Month' },
                { value: 'custom', label: 'Custom' },
              ].map(option => (
                <button
                  key={option.value}
                  onClick={() => setTimeRange(option.value)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    timeRange === option.value
                      ? 'bg-amber-500 text-white'
                      : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          {timeRange === 'custom' && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-[var(--text-secondary)] mb-2">Start Date</label>
                <input
                  type="date"
                  value={customStart}
                  onChange={e => setCustomStart(e.target.value)}
                  className="w-full rounded-lg px-4 py-2"
                />
              </div>
              <div>
                <label className="block text-sm text-[var(--text-secondary)] mb-2">End Date</label>
                <input
                  type="date"
                  value={customEnd}
                  onChange={e => setCustomEnd(e.target.value)}
                  className="w-full rounded-lg px-4 py-2"
                />
              </div>
            </div>
          )}

          <button
            onClick={() => generateNarrative.mutate()}
            disabled={generateNarrative.isPending}
            className="btn-primary px-6 py-3 rounded-lg w-full md:w-auto"
          >
            {generateNarrative.isPending ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Generating...
              </span>
            ) : (
              '📖 Generate Narrative'
            )}
          </button>
        </div>
      </div>

      {/* Error */}
      {generateNarrative.isError && (
        <div className="card p-4 border-red-500/50" style={{ background: 'rgba(239, 68, 68, 0.1)' }}>
          <div className="flex items-center gap-2 text-red-400">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {String(generateNarrative.error)}
          </div>
        </div>
      )}

      {/* Result */}
      {generateNarrative.data && (
        <div className="card p-6 animate-fade-in">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-[var(--text-primary)]">Your Story</h3>
            <div className="flex items-center gap-4 text-sm text-[var(--text-tertiary)]">
              <span>{generateNarrative.data.sources_count} sources</span>
              <span>
                {new Date(generateNarrative.data.generated_at).toLocaleString()}
              </span>
            </div>
          </div>

          <div
            className="prose prose-invert max-w-none"
            style={{
              color: 'var(--text-primary)',
              lineHeight: 1.8,
            }}
          >
            {generateNarrative.data.narrative.split('\n\n').map((paragraph, i) => (
              <p key={i} className="mb-4 last:mb-0">{paragraph}</p>
            ))}
          </div>

          {/* Actions */}
          <div className="mt-6 pt-4 border-t flex gap-3" style={{ borderColor: 'var(--border-primary)' }}>
            <button
              onClick={() => navigator.clipboard?.writeText(generateNarrative.data?.narrative || '')}
              className="btn-secondary px-4 py-2 rounded-lg text-sm flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              Copy
            </button>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!generateNarrative.data && !generateNarrative.isPending && (
        <div className="text-center py-16 text-[var(--text-tertiary)]">
          <div className="text-6xl mb-4">📖</div>
          <div className="font-medium text-lg text-[var(--text-primary)]">Ready to tell your story</div>
          <div className="text-sm mt-1 max-w-md mx-auto">
            Generate a narrative from your memories. The AI will weave together your experiences,
            preferences, and life events into a coherent story.
          </div>
        </div>
      )}
    </div>
  )
}
