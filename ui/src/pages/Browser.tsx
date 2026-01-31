import { useQuery } from '@tanstack/react-query'
import { apiGet, getPersistedUserId } from '@/lib/api'
import { useEffect, useMemo, useState } from 'react'
import clsx from 'clsx'

// Types
type MemoryResult = {
  id: string
  content: string
  layer: string
  type: string
  score?: number
  metadata?: {
    tags?: string[]
    timestamp?: string
    emotional_valence?: number
    emotional_arousal?: number
    dominant_emotion?: string
    portfolio?: {
      ticker?: string
      quantity?: number
      price?: number
      intent?: string
    }
    location?: { place?: string } | string
    participants?: string[]
    project?: { name?: string; status?: string }
    learning_journal?: { topic?: string; level?: string }
    relationship?: { person_name?: string; closeness?: string }
    [key: string]: unknown
  }
}

type RetrieveResult = {
  results: MemoryResult[]
  pagination?: { limit: number; offset: number; total?: number }
  finance?: {
    portfolio?: {
      holdings?: Array<{ ticker: string; shares: number; avg_price?: number }>
    }
  }
}

// Sentiment color helpers for dark theme
function getValenceColor(valence: number): string {
  if (valence >= 0.5) return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
  if (valence >= 0.2) return 'bg-green-500/20 text-green-400 border-green-500/30'
  if (valence > -0.2) return 'bg-neutral-500/20 text-neutral-400 border-neutral-500/30'
  if (valence > -0.5) return 'bg-orange-500/20 text-orange-400 border-orange-500/30'
  return 'bg-red-500/20 text-red-400 border-red-500/30'
}

function getValenceBorderColor(valence: number): string {
  if (valence >= 0.5) return 'border-l-emerald-500'
  if (valence >= 0.2) return 'border-l-green-500'
  if (valence > -0.2) return 'border-l-neutral-500'
  if (valence > -0.5) return 'border-l-orange-500'
  return 'border-l-red-500'
}

function getArousalIndicator(arousal: number): string {
  if (arousal >= 0.7) return '⚡'
  if (arousal >= 0.4) return '●'
  return '○'
}

function getEmotionEmoji(emotion?: string): string {
  const emotions: Record<string, string> = {
    joy: '😊', happiness: '😊', excited: '🤩', surprise: '😮',
    sadness: '😢', sad: '😢', anger: '😠', angry: '😠',
    fear: '😨', anxious: '😰', worried: '😟', frustrated: '😤',
    neutral: '😐', calm: '😌', love: '❤️', disgust: '🤢'
  }
  return emotions[emotion?.toLowerCase() || ''] || ''
}

function getLayerStyle(layer: string): string {
  const styles: Record<string, string> = {
    'short-term': 'badge-amber',
    'semantic': 'badge-blue',
    'long-term': 'badge-purple',
    'episodic': 'badge-cyan',
  }
  return styles[layer] || 'badge-neutral'
}

function getTypeStyle(type: string): string {
  return type === 'explicit' ? 'badge-green' : 'badge-purple'
}

// Statistics component
function Statistics({ memories }: { memories: MemoryResult[] }) {
  const stats = useMemo(() => {
    const byLayer: Record<string, number> = {}
    const byType: Record<string, number> = {}
    const byEmotion: Record<string, number> = {}
    let withSentiment = 0
    let totalValence = 0

    memories.forEach(m => {
      byLayer[m.layer] = (byLayer[m.layer] || 0) + 1
      byType[m.type] = (byType[m.type] || 0) + 1

      const emotion = m.metadata?.dominant_emotion
      if (emotion) {
        byEmotion[emotion] = (byEmotion[emotion] || 0) + 1
      }

      if (m.metadata?.emotional_valence !== undefined && m.metadata.emotional_valence !== 0) {
        withSentiment++
        totalValence += m.metadata.emotional_valence
      }
    })

    return {
      total: memories.length,
      byLayer,
      byType,
      byEmotion,
      avgValence: withSentiment > 0 ? totalValence / withSentiment : null,
      withSentiment
    }
  }, [memories])

  return (
    <div className="card p-5">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
        <div>
          <div className="stat-value text-gradient">{stats.total}</div>
          <div className="stat-label">Total Memories</div>
        </div>
        <div>
          <div className="text-sm space-y-1.5">
            {Object.entries(stats.byLayer).map(([layer, count]) => (
              <div key={layer} className="flex items-center gap-2">
                <span className={clsx('badge', getLayerStyle(layer))}>{layer}</span>
                <span className="text-[var(--text-secondary)] font-medium">{count}</span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <div className="text-sm space-y-1.5">
            {Object.entries(stats.byType).map(([type, count]) => (
              <div key={type} className="flex items-center gap-2">
                <span className={clsx('badge', getTypeStyle(type))}>{type}</span>
                <span className="text-[var(--text-secondary)] font-medium">{count}</span>
              </div>
            ))}
          </div>
        </div>
        <div>
          {stats.avgValence !== null && (
            <div>
              <div className={clsx('inline-block px-3 py-1.5 rounded-lg text-sm font-medium border', getValenceColor(stats.avgValence))}>
                {stats.avgValence >= 0 ? '+' : ''}{stats.avgValence.toFixed(2)} avg
              </div>
              <div className="text-xs text-[var(--text-tertiary)] mt-1.5">{stats.withSentiment} with sentiment</div>
            </div>
          )}
          {Object.keys(stats.byEmotion).length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {Object.entries(stats.byEmotion).slice(0, 4).map(([emotion, count]) => (
                <span key={emotion} className="text-xs px-2 py-1 rounded-lg" style={{ background: 'var(--bg-tertiary)' }}>
                  {getEmotionEmoji(emotion)} {count}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// Memory Card component
function MemoryCard({ memory, onCopy }: { memory: MemoryResult; onCopy: (text: string) => void }) {
  const [expanded, setExpanded] = useState(false)
  const meta = memory.metadata || {}
  const hasValence = meta.emotional_valence !== undefined && meta.emotional_valence !== 0
  const hasArousal = meta.emotional_arousal !== undefined && meta.emotional_arousal !== 0
  const hasSentiment = hasValence || hasArousal || meta.dominant_emotion

  const timestamp = meta.timestamp ? new Date(meta.timestamp as string) : null
  const tags = Array.isArray(meta.tags) ? meta.tags : []
  const portfolio = meta.portfolio
  const location = typeof meta.location === 'string' ? meta.location : meta.location?.place
  const participants = Array.isArray(meta.participants) ? meta.participants : []
  const project = meta.project
  const learning = meta.learning_journal
  const relationship = meta.relationship

  return (
    <div className={clsx(
      'memory-card',
      hasSentiment && 'has-sentiment',
      hasValence && (meta.emotional_valence! >= 0.2 ? 'positive' : meta.emotional_valence! <= -0.2 ? 'negative' : 'neutral')
    )}>
      {/* Header row */}
      <div className="flex items-start gap-3">
        {/* Sentiment indicator */}
        {hasSentiment && (
          <div className="flex flex-col items-center gap-1 min-w-[40px]">
            <span className="text-xl">{getEmotionEmoji(meta.dominant_emotion)}</span>
            <span className="text-xs text-[var(--text-tertiary)]">
              {getArousalIndicator(meta.emotional_arousal || 0)}
            </span>
          </div>
        )}

        {/* Main content */}
        <div className="flex-1 min-w-0">
          <p className="text-[var(--text-primary)] leading-relaxed">{memory.content}</p>

          {/* Tags */}
          {tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {tags.map((tag, i) => (
                <span key={i} className="px-2 py-0.5 rounded-full text-xs" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>
                  {tag}
                </span>
              ))}
            </div>
          )}

          {/* Structured data badges */}
          <div className="flex flex-wrap gap-2 mt-3">
            {portfolio?.ticker && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#34d399' }}>
                📈 {portfolio.ticker}
                {portfolio.quantity && <span style={{ color: '#10b981' }}>×{portfolio.quantity}</span>}
                {portfolio.intent && <span style={{ color: '#6ee7b7' }}>({portfolio.intent})</span>}
              </span>
            )}
            {project?.name && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs" style={{ background: 'rgba(99, 102, 241, 0.15)', color: '#a5b4fc' }}>
                📁 {project.name}
                {project.status && <span style={{ color: '#818cf8' }}>• {project.status}</span>}
              </span>
            )}
            {learning?.topic && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24' }}>
                📚 {learning.topic}
                {learning.level && <span style={{ color: '#f59e0b' }}>• {learning.level}</span>}
              </span>
            )}
            {relationship?.person_name && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs" style={{ background: 'rgba(236, 72, 153, 0.15)', color: '#f472b6' }}>
                👤 {relationship.person_name}
                {relationship.closeness && <span style={{ color: '#ec4899' }}>• {relationship.closeness}</span>}
              </span>
            )}
            {location && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs" style={{ background: 'rgba(34, 211, 238, 0.15)', color: '#22d3ee' }}>
                📍 {location}
              </span>
            )}
            {participants.length > 0 && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs" style={{ background: 'rgba(139, 92, 246, 0.15)', color: '#a78bfa' }}>
                👥 {participants.join(', ')}
              </span>
            )}
          </div>
        </div>

        {/* Right column - metadata */}
        <div className="flex flex-col items-end gap-1.5 text-xs shrink-0">
          <span className={clsx('badge', getLayerStyle(memory.layer))}>
            {memory.layer}
          </span>
          <span className={clsx('badge', getTypeStyle(memory.type))}>
            {memory.type}
          </span>
          {hasSentiment && (
            <span className={clsx('px-2 py-0.5 rounded border text-xs', getValenceColor(meta.emotional_valence || 0))}>
              {(meta.emotional_valence || 0) >= 0 ? '+' : ''}{(meta.emotional_valence || 0).toFixed(1)}
            </span>
          )}
          {memory.score !== undefined && (
            <span className="text-[var(--text-tertiary)]">
              {(memory.score * 100).toFixed(0)}% match
            </span>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between mt-4 pt-3 border-t" style={{ borderColor: 'var(--border-primary)' }}>
        <div className="text-xs text-[var(--text-tertiary)]">
          {timestamp && timestamp.toLocaleString()}
          <span className="ml-2 font-mono" style={{ color: 'var(--text-tertiary)', opacity: 0.5 }}>{memory.id.slice(0, 16)}...</span>
        </div>
        <div className="flex items-center gap-3">
          <button
            className="text-xs text-[var(--accent-secondary)] hover:text-[var(--accent-primary)] transition-colors"
            onClick={() => onCopy(memory.id)}
          >
            Copy ID
          </button>
          <button
            className="text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? 'Hide' : 'Show'} raw
          </button>
        </div>
      </div>

      {/* Expanded raw view */}
      {expanded && (
        <pre className="mt-3 p-4 rounded-lg text-xs overflow-auto max-h-64 font-mono" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>
          {JSON.stringify(memory, null, 2)}
        </pre>
      )}
    </div>
  )
}

// Main Browser component
export function Browser() {
  const [userId, setUserId] = useState('')
  const [query, setQuery] = useState('')
  const [layer, setLayer] = useState('')
  const [type, setType] = useState('')
  const [sort, setSort] = useState('newest')
  const [limit, setLimit] = useState(50)
  const [offset, setOffset] = useState(0)
  const [viewMode, setViewMode] = useState<'cards' | 'timeline'>('cards')

  useEffect(() => { setUserId(getPersistedUserId()) }, [])

  const url = useMemo(() => {
    const params = new URLSearchParams()
    params.set('user_id', userId)
    if (query.trim()) params.set('query', query.trim())
    if (layer) params.set('layer', layer)
    if (type) params.set('type', type)
    if (sort) params.set('sort', sort)
    params.set('limit', String(limit))
    params.set('offset', String(offset))
    return `/v1/retrieve?${params.toString()}`
  }, [userId, query, layer, type, sort, limit, offset])

  const { data, isFetching, isError, error, refetch } = useQuery({
    queryKey: ['browser', url],
    queryFn: () => apiGet<RetrieveResult>(url),
    enabled: !!userId,
  })

  function copy(text: string) {
    navigator.clipboard?.writeText(text).then(() => {
      // Could add toast notification here
    }).catch(() => {})
  }

  function exportJson() {
    if (!data) return
    const blob = new Blob([JSON.stringify(data.results, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `memories_${userId}_${new Date().toISOString().slice(0, 10)}.json`
    a.click()
  }

  // Group memories by date for timeline view
  const memoriesByDate = useMemo(() => {
    if (!data?.results || !Array.isArray(data.results)) return new Map<string, MemoryResult[]>()
    const grouped = new Map<string, MemoryResult[]>()

    data.results.forEach(m => {
      const ts = m.metadata?.timestamp
      const dateKey = ts ? new Date(ts as string).toLocaleDateString() : 'Unknown Date'
      if (!grouped.has(dateKey)) grouped.set(dateKey, [])
      grouped.get(dateKey)!.push(m)
    })

    return grouped
  }, [data?.results])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-[var(--text-primary)]">Memory Browser</h2>
          <p className="text-[var(--text-secondary)]">Search and explore your memories</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setViewMode('cards')}
            className={clsx(
              'px-4 py-2 rounded-lg text-sm font-medium transition-all',
              viewMode === 'cards'
                ? 'btn-primary'
                : 'btn-secondary'
            )}
          >
            Cards
          </button>
          <button
            onClick={() => setViewMode('timeline')}
            className={clsx(
              'px-4 py-2 rounded-lg text-sm font-medium transition-all',
              viewMode === 'timeline'
                ? 'btn-primary'
                : 'btn-secondary'
            )}
          >
            Timeline
          </button>
        </div>
      </div>

      {/* Search bar */}
      <div className="flex gap-3">
        <div className="relative flex-1">
          <input
            className="w-full rounded-lg px-4 py-3 pl-11"
            style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)' }}
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search memories semantically..."
            onKeyDown={e => e.key === 'Enter' && refetch()}
          />
          <svg className="absolute left-4 top-3.5 h-5 w-5 text-[var(--text-tertiary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
        <button
          onClick={() => refetch()}
          disabled={!userId || isFetching}
          className="btn-primary px-6 py-3 rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isFetching ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Loading
            </span>
          ) : 'Search'}
        </button>
      </div>

      {/* Filters */}
      <div className="card p-4">
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex items-center gap-2">
            <label className="text-sm text-[var(--text-tertiary)] font-medium">Layer:</label>
            <select
              className="rounded-lg px-3 py-2 text-sm"
              style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)' }}
              value={layer}
              onChange={e => setLayer(e.target.value)}
            >
              <option value="">All</option>
              <option value="short-term">Short-term</option>
              <option value="semantic">Semantic</option>
              <option value="long-term">Long-term</option>
              <option value="episodic">Episodic</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-sm text-[var(--text-tertiary)] font-medium">Type:</label>
            <select
              className="rounded-lg px-3 py-2 text-sm"
              style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)' }}
              value={type}
              onChange={e => setType(e.target.value)}
            >
              <option value="">All</option>
              <option value="explicit">Explicit</option>
              <option value="implicit">Implicit</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-sm text-[var(--text-tertiary)] font-medium">Sort:</label>
            <select
              className="rounded-lg px-3 py-2 text-sm"
              style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)' }}
              value={sort}
              onChange={e => setSort(e.target.value)}
            >
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="">Relevance</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-sm text-[var(--text-tertiary)] font-medium">Show:</label>
            <select
              className="rounded-lg px-3 py-2 text-sm"
              style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)' }}
              value={limit}
              onChange={e => setLimit(parseInt(e.target.value))}
            >
              <option value="20">20</option>
              <option value="50">50</option>
              <option value="100">100</option>
              <option value="200">200</option>
              <option value="500">500</option>
              <option value="1000">1000</option>
              <option value="3000">3000</option>
            </select>
          </div>

          <div className="ml-auto">
            <button
              onClick={exportJson}
              className="btn-secondary px-4 py-2 rounded-lg text-sm flex items-center gap-2"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Export
            </button>
          </div>
        </div>
      </div>

      {/* Error */}
      {isError && (
        <div className="p-4 rounded-lg flex items-center gap-3" style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#f87171' }}>
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {String(error)}
        </div>
      )}

      {/* Statistics */}
      {data?.results && Array.isArray(data.results) && data.results.length > 0 && (
        <Statistics memories={data.results} />
      )}

      {/* Portfolio Summary (if present) */}
      {data?.finance?.portfolio?.holdings && Array.isArray(data.finance.portfolio.holdings) && data.finance.portfolio.holdings.length > 0 && (
        <div className="card p-5" style={{ background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(6, 95, 70, 0.1))' }}>
          <h3 className="font-medium text-emerald-400 mb-3 flex items-center gap-2">
            <span>📊</span> Portfolio Holdings
          </h3>
          <div className="flex flex-wrap gap-2">
            {data.finance.portfolio.holdings.map((h, i) => (
              <span key={i} className="px-3 py-1.5 rounded-lg text-sm" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)' }}>
                <span className="font-semibold text-[var(--text-primary)]">{h.ticker}</span>
                <span className="text-emerald-400 ml-1.5">×{h.shares}</span>
                {h.avg_price && <span className="text-[var(--text-tertiary)] ml-1.5">@${h.avg_price.toFixed(2)}</span>}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Results count */}
      {data?.results && Array.isArray(data.results) && (
        <div className="text-sm text-[var(--text-secondary)]">
          Showing <span className="font-medium text-[var(--text-primary)]">{data.results.length}</span> memories
          {data.pagination?.total && <> of <span className="font-medium text-[var(--text-primary)]">{data.pagination.total}</span></>}
          {offset > 0 && <span className="text-[var(--text-tertiary)]"> (offset: {offset})</span>}
        </div>
      )}

      {/* Memory list - Cards view */}
      {viewMode === 'cards' && data?.results && Array.isArray(data.results) && (
        <div className="space-y-3">
          {data.results.map(m => (
            <MemoryCard key={m.id} memory={m} onCopy={copy} />
          ))}
        </div>
      )}

      {/* Memory list - Timeline view */}
      {viewMode === 'timeline' && data?.results && Array.isArray(data.results) && (
        <div className="relative">
          {/* Timeline line */}
          <div className="absolute left-4 top-0 bottom-0 w-0.5" style={{ background: 'linear-gradient(to bottom, var(--accent-primary), var(--accent-secondary), var(--accent-primary))' }} />

          <div className="space-y-8">
            {Array.from(memoriesByDate.entries()).map(([date, memories]) => (
              <div key={date} className="relative">
                {/* Date marker */}
                <div className="flex items-center gap-4 mb-4">
                  <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold z-10 shadow-lg glow" style={{ background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))', color: 'white' }}>
                    {memories.length}
                  </div>
                  <div className="font-semibold text-[var(--text-primary)]">{date}</div>
                </div>

                {/* Memories for this date */}
                <div className="ml-12 space-y-3">
                  {memories.map(m => (
                    <MemoryCard key={m.id} memory={m} onCopy={copy} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {data?.results && Array.isArray(data.results) && data.results.length === 0 && (
        <div className="text-center py-16">
          <div className="text-5xl mb-4">🧠</div>
          <div className="font-semibold text-lg text-[var(--text-primary)]">No memories found</div>
          <div className="text-sm mt-2 text-[var(--text-secondary)]">Try adjusting your search query or filters</div>
        </div>
      )}

      {/* Loading state */}
      {isFetching && !data && (
        <div className="text-center py-16">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-2 border-t-transparent" style={{ borderColor: 'var(--accent-primary)', borderTopColor: 'transparent' }} />
          <div className="mt-4 text-[var(--text-secondary)]">Loading memories...</div>
        </div>
      )}

      {/* Pagination */}
      {data?.results && Array.isArray(data.results) && data.results.length > 0 && (
        <div className="flex items-center justify-center gap-3 pt-6">
          <button
            onClick={() => setOffset(Math.max(0, offset - limit))}
            disabled={offset === 0}
            className="btn-secondary px-4 py-2 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Previous
          </button>
          <span className="px-4 py-2 text-sm text-[var(--text-secondary)] font-medium">
            Page {Math.floor(offset / limit) + 1}
          </span>
          <button
            onClick={() => setOffset(offset + limit)}
            disabled={data.results.length < limit}
            className="btn-secondary px-4 py-2 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            Next
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      )}
    </div>
  )
}
