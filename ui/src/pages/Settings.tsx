import { useQuery } from '@tanstack/react-query'
import { apiGet, getPersistedUserId, API_BASE } from '@/lib/api'
import { useEffect, useState } from 'react'
import clsx from 'clsx'

type HealthCheck = {
  status: string
  version?: string
  databases?: Record<string, {
    status: string
    latency_ms?: number
  }>
}

export function Settings() {
  const [userId, setUserId] = useState('')
  useEffect(() => { setUserId(getPersistedUserId()) }, [])

  const { data: health, isLoading, refetch } = useQuery({
    queryKey: ['health'],
    queryFn: () => apiGet<HealthCheck>('/health'),
    refetchInterval: 30000, // Refresh every 30 seconds
  })

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'healthy':
      case 'ok':
      case 'connected':
        return 'bg-emerald-500'
      case 'degraded':
      case 'warning':
        return 'bg-amber-500'
      case 'unhealthy':
      case 'error':
      case 'disconnected':
        return 'bg-red-500'
      default:
        return 'bg-gray-500'
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-semibold text-[var(--text-primary)]">Settings</h2>
        <p className="text-[var(--text-secondary)]">System health and configuration</p>
      </div>

      {/* API Configuration */}
      <div className="card p-5">
        <h3 className="text-lg font-medium text-[var(--text-primary)] mb-4">API Configuration</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-[var(--text-tertiary)] mb-1">API Base URL</label>
            <div className="p-3 rounded-lg font-mono text-sm" style={{ background: 'var(--bg-tertiary)' }}>
              {API_BASE}
            </div>
          </div>
          <div>
            <label className="block text-sm text-[var(--text-tertiary)] mb-1">Current User ID</label>
            <div className="p-3 rounded-lg font-mono text-sm" style={{ background: 'var(--bg-tertiary)' }}>
              {userId || 'Not set'}
            </div>
          </div>
        </div>
      </div>

      {/* Health Check */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium text-[var(--text-primary)]">System Health</h3>
          <button
            onClick={() => refetch()}
            className="btn-secondary px-3 py-1.5 rounded-lg text-sm"
          >
            Refresh
          </button>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-2 border-amber-500 border-t-transparent" />
          </div>
        ) : health ? (
          <div className="space-y-4">
            {/* Overall Status */}
            <div className="flex items-center gap-3 p-4 rounded-lg" style={{ background: 'var(--bg-tertiary)' }}>
              <div className={clsx('w-3 h-3 rounded-full', getStatusColor(health.status))} />
              <div>
                <div className="font-medium text-[var(--text-primary)]">API Status</div>
                <div className="text-sm text-[var(--text-secondary)]">
                  {health.status} {health.version && `• v${health.version}`}
                </div>
              </div>
            </div>

            {/* Database Status */}
            {health.databases && (
              <div className="space-y-2">
                <div className="text-sm text-[var(--text-tertiary)]">Database Connections</div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {Object.entries(health.databases).map(([name, db]) => (
                    <div
                      key={name}
                      className="p-3 rounded-lg flex items-center gap-3"
                      style={{ background: 'var(--bg-tertiary)' }}
                    >
                      <div className={clsx('w-2.5 h-2.5 rounded-full', getStatusColor(db.status))} />
                      <div className="flex-1">
                        <div className="text-sm font-medium text-[var(--text-primary)] capitalize">{name}</div>
                        <div className="text-xs text-[var(--text-tertiary)]">
                          {db.status}
                          {db.latency_ms !== undefined && ` • ${db.latency_ms}ms`}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="text-center py-8 text-[var(--text-tertiary)]">
            <div className="text-3xl mb-2">⚠️</div>
            <p>Unable to fetch health status</p>
          </div>
        )}
      </div>

      {/* Data Management */}
      <div className="card p-5">
        <h3 className="text-lg font-medium text-[var(--text-primary)] mb-4">Data Management</h3>
        <div className="space-y-4">
          <div className="p-4 rounded-lg border" style={{ borderColor: 'var(--border-primary)', background: 'var(--bg-tertiary)' }}>
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium text-[var(--text-primary)]">Export All Data</div>
                <div className="text-sm text-[var(--text-tertiary)]">Download all memories, profile, and portfolio data</div>
              </div>
              <button className="btn-secondary px-4 py-2 rounded-lg text-sm">
                Export JSON
              </button>
            </div>
          </div>

          <div className="p-4 rounded-lg border border-red-500/30" style={{ background: 'rgba(239, 68, 68, 0.1)' }}>
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium text-red-400">Delete All Data</div>
                <div className="text-sm text-[var(--text-tertiary)]">Permanently delete all data for this user</div>
              </div>
              <button className="px-4 py-2 rounded-lg text-sm bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors">
                Delete
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* About */}
      <div className="card p-5">
        <h3 className="text-lg font-medium text-[var(--text-primary)] mb-4">About</h3>
        <div className="text-sm text-[var(--text-secondary)] space-y-2">
          <p>
            <strong className="text-[var(--text-primary)]">Agentic Memories</strong> is a sophisticated
            memory system that mirrors human consciousness for AI applications.
          </p>
          <p>
            It provides a six-layer memory hierarchy including episodic, semantic, procedural,
            emotional, portfolio, and identity layers, with polyglot persistence across
            multiple specialized databases.
          </p>
        </div>
      </div>
    </div>
  )
}
