import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, getPersistedUserId } from '@/lib/api'
import { useEffect, useState } from 'react'
import clsx from 'clsx'

type Intent = Record<string, unknown>

// Helper to safely extract intent fields
function getField(intent: Intent, field: string): unknown {
  const value = intent[field]
  if (value === null || value === undefined) return null
  if (typeof value === 'object' && 'value' in value) {
    return (value as { value: unknown }).value
  }
  return value
}

function getStringField(intent: Intent, field: string): string {
  const value = getField(intent, field)
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value
  return ''
}

function getDateField(intent: Intent, field: string): Date | null {
  const value = getField(intent, field)
  if (!value) return null

  // Handle nested schedule objects
  if (typeof value === 'object' && value !== null) {
    const obj = value as Record<string, unknown>
    if (obj.trigger_at) return new Date(obj.trigger_at as string)
  }

  if (typeof value === 'string') {
    const date = new Date(value)
    return isNaN(date.getTime()) ? null : date
  }
  return null
}

function isActiveIntent(intent: Intent): boolean {
  const status = getStringField(intent, 'status')
  if (status === 'completed' || status === 'expired' || status === 'inactive') {
    return false
  }

  // Check trigger schedule for expiration
  const triggerSchedule = getField(intent, 'trigger_schedule')
  if (triggerSchedule && typeof triggerSchedule === 'object') {
    const schedule = triggerSchedule as Record<string, unknown>
    if (schedule.trigger_at) {
      const triggerDate = new Date(schedule.trigger_at as string)
      if (triggerDate < new Date()) return false
    }
  }

  return true
}

function formatSchedule(intent: Intent): string {
  const triggerSchedule = getField(intent, 'trigger_schedule')
  if (triggerSchedule && typeof triggerSchedule === 'object') {
    const schedule = triggerSchedule as Record<string, unknown>
    if (schedule.trigger_at) {
      return new Date(schedule.trigger_at as string).toLocaleString()
    }
  }

  const nextFire = getDateField(intent, 'next_fire_at')
  if (nextFire) return nextFire.toLocaleString()

  const scheduleCron = getStringField(intent, 'schedule_cron')
  if (scheduleCron) return `Cron: ${scheduleCron}`

  return '—'
}

function extractActionContext(intent: Intent): Record<string, string> {
  const context: Record<string, string> = {}
  const actionContext = getField(intent, 'action_context')

  if (actionContext && typeof actionContext === 'object') {
    const ac = actionContext as Record<string, unknown>
    if (ac.intent_summary) context['Summary'] = String(ac.intent_summary)
    if (ac.original_request) context['Request'] = String(ac.original_request)
    if (ac.message_guidance) context['Guidance'] = String(ac.message_guidance)
  }

  return context
}

export function Intents() {
  const [userId, setUserId] = useState('')
  const [showInactive, setShowInactive] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const queryClient = useQueryClient()

  useEffect(() => { setUserId(getPersistedUserId()) }, [])

  const { data: intents, isLoading } = useQuery({
    queryKey: ['intents', userId],
    queryFn: () => apiGet<Intent[]>(`/v1/intents?user_id=${userId}`),
    enabled: !!userId,
  })

  const { data: pendingIntents } = useQuery({
    queryKey: ['intents-pending', userId],
    queryFn: () => apiGet<Intent[]>(`/v1/intents/pending?user_id=${userId}`),
    enabled: !!userId,
  })

  const fireIntent = useMutation({
    mutationFn: (intentId: string) => apiPost(`/v1/intents/${intentId}/fire`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['intents', userId] })
      queryClient.invalidateQueries({ queryKey: ['intents-pending', userId] })
    },
  })

  // Filter and sort intents
  const filteredIntents = (intents || [])
    .filter(intent => showInactive || isActiveIntent(intent))
    .sort((a, b) => {
      // Active first, then by date
      const aActive = isActiveIntent(a)
      const bActive = isActiveIntent(b)
      if (aActive !== bActive) return aActive ? -1 : 1

      const aDate = getDateField(a, 'created_at')
      const bDate = getDateField(b, 'created_at')
      if (aDate && bDate) return bDate.getTime() - aDate.getTime()
      return 0
    })

  const activeCount = (intents || []).filter(isActiveIntent).length
  const inactiveCount = (intents || []).length - activeCount

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
          <h2 className="text-2xl font-semibold text-[var(--text-primary)]">Intents</h2>
          <p className="text-[var(--text-secondary)]">Scheduled actions and triggers</p>
        </div>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(e) => setShowInactive(e.target.checked)}
            className="w-4 h-4 rounded"
          />
          <span className="text-sm text-[var(--text-secondary)]">
            Show inactive ({inactiveCount})
          </span>
        </label>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="stat-card">
          <div className="stat-value text-amber-500">{intents?.length || 0}</div>
          <div className="stat-label">Total Intents</div>
        </div>
        <div className="stat-card">
          <div className="stat-value text-emerald-500">{activeCount}</div>
          <div className="stat-label">Active</div>
        </div>
        <div className="stat-card">
          <div className="stat-value text-blue-500">{pendingIntents?.length || 0}</div>
          <div className="stat-label">Pending</div>
        </div>
      </div>

      {/* Intents Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr style={{ background: 'var(--bg-tertiary)' }}>
                <th className="text-left px-4 py-3 text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">Name</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">Type</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">Action</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">Scheduled</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">Status</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y" style={{ borderColor: 'var(--border-primary)' }}>
              {filteredIntents.length > 0 ? (
                filteredIntents.map((intent, idx) => {
                  const id = getStringField(intent, 'id') || String(idx)
                  const name = getStringField(intent, 'intent_name') || getStringField(intent, 'name') || getStringField(intent, 'description') || 'Unnamed'
                  const triggerType = getStringField(intent, 'trigger_type') || '—'
                  const actionType = getStringField(intent, 'action_type') || '—'
                  const schedule = formatSchedule(intent)
                  const isActive = isActiveIntent(intent)
                  const actionContext = extractActionContext(intent)
                  const isExpanded = expandedId === id

                  return (
                    <>
                      <tr
                        key={id}
                        className={clsx(
                          'hover:bg-[var(--bg-tertiary)] transition-colors cursor-pointer',
                          !isActive && 'opacity-50'
                        )}
                        onClick={() => setExpandedId(isExpanded ? null : id)}
                      >
                        <td className="px-4 py-3">
                          <div className="font-medium text-[var(--text-primary)]">{name}</div>
                        </td>
                        <td className="px-4 py-3">
                          <span className="badge badge-blue">{triggerType}</span>
                        </td>
                        <td className="px-4 py-3">
                          <span className="badge badge-purple">{actionType}</span>
                        </td>
                        <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                          {schedule}
                        </td>
                        <td className="px-4 py-3">
                          <span className={clsx(
                            'badge',
                            isActive ? 'badge-green' : 'badge-neutral'
                          )}>
                            {isActive ? 'Active' : 'Expired'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          {isActive && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                fireIntent.mutate(id)
                              }}
                              disabled={fireIntent.isPending}
                              className="btn-secondary px-3 py-1.5 rounded-lg text-sm"
                            >
                              Fire
                            </button>
                          )}
                        </td>
                      </tr>
                      {isExpanded && Object.keys(actionContext).length > 0 && (
                        <tr key={`${id}-expanded`}>
                          <td colSpan={6} className="px-4 py-3" style={{ background: 'var(--bg-tertiary)' }}>
                            <div className="space-y-2">
                              {Object.entries(actionContext).map(([key, value]) => (
                                <div key={key}>
                                  <span className="text-xs text-[var(--text-tertiary)] uppercase">{key}: </span>
                                  <span className="text-sm text-[var(--text-primary)]">{value}</span>
                                </div>
                              ))}
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  )
                })
              ) : (
                <tr>
                  <td colSpan={6} className="text-center py-16 text-[var(--text-tertiary)]">
                    <div className="text-5xl mb-3">⏰</div>
                    <div className="font-medium text-lg text-[var(--text-primary)]">
                      {showInactive ? 'No intents yet' : 'No active intents'}
                    </div>
                    <div className="text-sm mt-1">
                      {!showInactive && inactiveCount > 0 && (
                        <button
                          onClick={() => setShowInactive(true)}
                          className="text-amber-500 hover:text-amber-400"
                        >
                          Show {inactiveCount} inactive intent{inactiveCount !== 1 ? 's' : ''}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
