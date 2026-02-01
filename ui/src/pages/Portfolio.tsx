import { useQuery } from '@tanstack/react-query'
import { apiGet, getPersistedUserId } from '@/lib/api'
import { useEffect, useState } from 'react'

type Holding = {
  ticker: string
  asset_name?: string
  shares: number
  avg_price?: number
  first_acquired?: string
  last_updated?: string
}

type PortfolioData = {
  user_id: string
  holdings: Holding[]
  total_holdings: number
  last_updated?: string
}

export function Portfolio() {
  const [userId, setUserId] = useState('')
  useEffect(() => { setUserId(getPersistedUserId()) }, [])

  const { data: portfolio, isLoading, refetch } = useQuery({
    queryKey: ['portfolio', userId],
    queryFn: () => apiGet<PortfolioData>(`/v1/portfolio?user_id=${userId}`),
    enabled: !!userId,
  })

  // Calculate portfolio stats
  const totalValue = portfolio?.holdings?.reduce((sum, h) => {
    return sum + ((h.shares || 0) * (h.avg_price || 0))
  }, 0) || 0

  const totalShares = portfolio?.holdings?.reduce((sum, h) => sum + (h.shares || 0), 0) || 0

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
          <h2 className="text-2xl font-semibold text-[var(--text-primary)]">Portfolio</h2>
          <p className="text-[var(--text-secondary)]">Track your investments</p>
        </div>
        <button
          onClick={() => refetch()}
          className="btn-secondary px-4 py-2 rounded-lg"
        >
          Refresh
        </button>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="stat-card">
          <div className="stat-value text-emerald-500">{portfolio?.total_holdings || 0}</div>
          <div className="stat-label">Holdings</div>
        </div>
        <div className="stat-card">
          <div className="stat-value text-blue-500">{totalShares.toLocaleString()}</div>
          <div className="stat-label">Total Shares</div>
        </div>
        <div className="stat-card">
          <div className="stat-value text-amber-500">${totalValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
          <div className="stat-label">Cost Basis</div>
        </div>
        <div className="stat-card">
          <div className="stat-value text-purple-500">
            ${totalValue > 0 && portfolio?.total_holdings ? (totalValue / portfolio.total_holdings).toFixed(0) : 0}
          </div>
          <div className="stat-label">Avg Position</div>
        </div>
      </div>

      {/* Holdings Table */}
      <div className="card overflow-hidden">
        <div className="p-4 border-b" style={{ borderColor: 'var(--border-primary)' }}>
          <h3 className="text-lg font-medium text-[var(--text-primary)]">Holdings</h3>
        </div>

        {portfolio?.holdings && portfolio.holdings.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr style={{ background: 'var(--bg-tertiary)' }}>
                  <th className="px-4 py-3 text-left text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
                    Symbol
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
                    Name
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
                    Shares
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
                    Avg Price
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
                    Value
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
                    First Acquired
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: 'var(--border-primary)' }}>
                {portfolio.holdings.map((holding, i) => {
                  const value = (holding.shares || 0) * (holding.avg_price || 0)
                  const percentage = totalValue > 0 ? (value / totalValue) * 100 : 0

                  return (
                    <tr
                      key={i}
                      className="transition-colors"
                      style={{ borderColor: 'var(--border-primary)' }}
                    >
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-emerald-500/20 to-emerald-600/20 flex items-center justify-center">
                            <span className="text-emerald-400 text-sm font-bold">
                              {holding.ticker?.slice(0, 2)}
                            </span>
                          </div>
                          <div>
                            <div className="font-medium text-[var(--text-primary)]">{holding.ticker}</div>
                            <div className="text-xs text-[var(--text-tertiary)]">{percentage.toFixed(1)}% of portfolio</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-4 text-[var(--text-secondary)]">
                        {holding.asset_name || '—'}
                      </td>
                      <td className="px-4 py-4 text-right font-mono text-[var(--text-primary)]">
                        {holding.shares?.toLocaleString()}
                      </td>
                      <td className="px-4 py-4 text-right font-mono text-[var(--text-secondary)]">
                        {holding.avg_price ? `$${holding.avg_price.toFixed(2)}` : '—'}
                      </td>
                      <td className="px-4 py-4 text-right font-mono text-[var(--text-primary)]">
                        ${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                      </td>
                      <td className="px-4 py-4 text-right text-[var(--text-tertiary)] text-sm">
                        {holding.first_acquired ? new Date(holding.first_acquired).toLocaleDateString() : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-16 text-[var(--text-tertiary)]">
            <div className="text-5xl mb-3">📊</div>
            <div className="font-medium text-lg text-[var(--text-primary)]">No holdings yet</div>
            <div className="text-sm mt-1">Start tracking your investments</div>
          </div>
        )}
      </div>

      {/* Portfolio Composition */}
      {portfolio?.holdings && portfolio.holdings.length > 0 && (
        <div className="card p-5">
          <h3 className="text-lg font-medium text-[var(--text-primary)] mb-4">Composition</h3>
          <div className="space-y-3">
            {portfolio.holdings
              .sort((a, b) => ((b.shares || 0) * (b.avg_price || 0)) - ((a.shares || 0) * (a.avg_price || 0)))
              .map((holding, i) => {
                const value = (holding.shares || 0) * (holding.avg_price || 0)
                const percentage = totalValue > 0 ? (value / totalValue) * 100 : 0

                return (
                  <div key={i}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm text-[var(--text-primary)]">{holding.ticker}</span>
                      <span className="text-sm text-[var(--text-secondary)]">{percentage.toFixed(1)}%</span>
                    </div>
                    <div className="h-2 rounded-full" style={{ background: 'var(--bg-tertiary)' }}>
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-emerald-400"
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                )
              })}
          </div>
        </div>
      )}
    </div>
  )
}
