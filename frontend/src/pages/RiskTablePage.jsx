import { useEffect, useMemo, useState } from 'react'
import { api, handleAuthError } from '../api'

function RiskTablePage() {
  const [buyers, setBuyers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [riskFilter, setRiskFilter] = useState('All')
  const [search, setSearch] = useState('')

  useEffect(() => {
    const load = async () => {
      try {
        const res = await api.get('/buyers')
        setBuyers(res.data)
      } catch (err) {
        if (handleAuthError(err)) return
        setError('Failed to load buyer risk table.')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const rows = useMemo(() => {
    let list = [...buyers]
    if (riskFilter !== 'All') {
      list = list.filter((b) => b.risk_classification === riskFilter)
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      list = list.filter((b) => b.buyer_name.toLowerCase().includes(q))
    }
    return list.sort((a, b) => a.reliability_score - b.reliability_score)
  }, [buyers, riskFilter, search])

  if (loading) return <div className="muted-text">Loading risk table…</div>
  if (error) return <div className="error-banner">{error}</div>

  if (buyers.length === 0) {
    return (
      <div className="empty-state">
        <h2 className="page-title">Buyer Risk Table</h2>
        <p>No buyers yet. Upload transaction data or run the seed script.</p>
      </div>
    )
  }

  return (
    <div>
      <h2 className="page-title">Buyer Risk Table</h2>
      <p className="page-subtitle">
        Compare reliability scores across buyers. Lower scores mean higher payment risk.
      </p>

      <div className="toolbar">
        <input
          className="form-input"
          placeholder="Search buyer"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="form-input risk-filter"
          value={riskFilter}
          onChange={(e) => setRiskFilter(e.target.value)}
        >
          <option>All</option>
          <option>Low Risk</option>
          <option>Medium Risk</option>
          <option>High Risk</option>
        </select>
      </div>

      <div className="card">
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Buyer</th>
                <th>Transactions</th>
                <th>Avg Delay</th>
                <th>Late %</th>
                <th>Reliability</th>
                <th>Predicted Delay Prob.</th>
                <th>Risk</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((b) => (
                <tr key={b.buyer_name}>
                  <td>{b.buyer_name}</td>
                  <td>{b.transaction_count}</td>
                  <td>{b.average_delay.toFixed(1)} days</td>
                  <td>{b.late_payment_percentage.toFixed(1)}%</td>
                  <td>{b.reliability_score.toFixed(1)}</td>
                  <td>
                    {b.predicted_delay_probability != null
                      ? `${(b.predicted_delay_probability * 100).toFixed(1)}%`
                      : '—'}
                  </td>
                  <td>
                    <span
                      className={`risk-badge risk-${b.risk_classification
                        .replace(/\s/g, '-')
                        .toLowerCase()}`}
                    >
                      {b.risk_classification}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default RiskTablePage
