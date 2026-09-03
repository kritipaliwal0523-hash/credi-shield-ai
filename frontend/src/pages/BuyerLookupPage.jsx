import { useState } from 'react'
import { api, handleAuthError } from '../api'

function BuyerLookupPage() {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])
  const [prediction, setPrediction] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [agentMessage, setAgentMessage] = useState(null)
  const [agentLoading, setAgentLoading] = useState(false)
  const [agentError, setAgentError] = useState('')

  const handleSearch = async (e) => {
    e.preventDefault()
    if (!query.trim()) return
    setError('')
    setResult(null)
    setHistory([])
    setPrediction(null)
    setAgentMessage(null)
    setAgentError('')
    setLoading(true)
    try {
      const name = query.trim()
      const [lookupRes, historyRes] = await Promise.all([
        api.get(`/buyer/${encodeURIComponent(name)}`),
        api.get(`/buyer/${encodeURIComponent(name)}/history`),
      ])
      setResult(lookupRes.data)
      setHistory(historyRes.data)

      const predictRes = await api.post('/predict', {
        invoice_amount: lookupRes.data.invoice_amount_total
          ? lookupRes.data.invoice_amount_total / Math.max(lookupRes.data.transaction_count || 1, 1)
          : 10000,
        payment_term_days: 30,
        issue_month: new Date().getMonth() + 1,
        buyer_name: name,
      })
      setPrediction(predictRes.data)
    } catch (err) {
      if (handleAuthError(err)) return
      if (err.response?.status === 404) {
        setError('Buyer not found. Check the name or upload data first.')
      } else {
        setError('Failed to fetch buyer details.')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleDraftMessage = async () => {
    if (!result) return
    setAgentError('')
    setAgentLoading(true)
    try {
      const res = await api.post(`/buyer/${encodeURIComponent(result.buyer_name)}/agent-message`)
      setAgentMessage(res.data)
    } catch (err) {
      if (handleAuthError(err)) return
      setAgentError('Failed to draft message. Is the backend running?')
    } finally {
      setAgentLoading(false)
    }
  }

  return (
    <div>
      <h2 className="page-title">Buyer Lookup</h2>
      <p className="page-subtitle">
        Search for a buyer to view reliability metrics, payment history, and real-time risk prediction.
      </p>
      <form className="lookup-form" onSubmit={handleSearch}>
        <input
          type="text"
          className="form-input"
          placeholder="Enter buyer name"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button type="submit" className="primary-button" disabled={loading}>
          {loading ? 'Searching…' : 'Search'}
        </button>
      </form>
      {error && <div className="error-banner">{error}</div>}
      {result && (
        <div className="card">
          <h3>{result.buyer_name}</h3>
          <div className="metrics-grid">
            <div className="metric-card">
              <span className="metric-label">Reliability Score</span>
              <span className="metric-value">{result.reliability_score.toFixed(1)}</span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Avg Delay</span>
              <span className="metric-value">{result.average_delay.toFixed(1)} days</span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Stored Delay Prob.</span>
              <span className="metric-value">
                {result.predicted_delay_probability != null
                  ? `${(result.predicted_delay_probability * 100).toFixed(1)}%`
                  : '—'}
              </span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Risk Classification</span>
              <span className="metric-value">{result.risk_classification}</span>
            </div>
          </div>
          <div className="recommendation-box">
            <h4>Recommendation</h4>
            <p>{result.recommendation}</p>
          </div>
          {prediction && (
            <div className="recommendation-box" style={{ marginTop: 12 }}>
              <h4>Real-time Risk Prediction</h4>
              <p>
                Predicted late probability:{' '}
                <strong>{(prediction.predicted_delay_probability * 100).toFixed(1)}%</strong>
                {' · '}
                {prediction.risk_label}
              </p>
              <p className="muted-text">{prediction.recommendation}</p>
            </div>
          )}

          <div className="recommendation-box" style={{ marginTop: 12 }}>
            <h4>AI Collections Agent</h4>
            <p className="muted-text">
              Draft a risk-appropriate message for this buyer, grounded in their actual
              reliability data. You review and send it — nothing is sent automatically.
            </p>
            <button
              type="button"
              className="primary-button"
              onClick={handleDraftMessage}
              disabled={agentLoading}
              style={{ marginTop: 8 }}
            >
              {agentLoading ? 'Drafting…' : 'Draft message'}
            </button>
            {agentError && <div className="error-banner" style={{ marginTop: 8 }}>{agentError}</div>}
            {agentMessage && (
              <div style={{ marginTop: 12 }}>
                <p className="muted-text" style={{ marginBottom: 4 }}>
                  Generated by:{' '}
                  <strong>{agentMessage.generated_by === 'gemini'? 'Gemini': 'Rule-based fallback'}</strong>
                </p>
                <pre
                  style={{
                    whiteSpace: 'pre-wrap',
                    background: '#f8fafc',
                    border: '1px solid #e2e8f0',
                    borderRadius: 8,
                    padding: 12,
                    fontFamily: 'inherit',
                    fontSize: 14,
                  }}
                >
                  {agentMessage.message}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
      {history.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>Payment History</h3>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Invoice</th>
                  <th>Amount</th>
                  <th>Due</th>
                  <th>Paid</th>
                  <th>Delay (days)</th>
                </tr>
              </thead>
              <tbody>
                {history.map((tx) => (
                  <tr key={tx.invoice_id}>
                    <td>{tx.invoice_id}</td>
                    <td>{tx.invoice_amount.toLocaleString()}</td>
                    <td>{tx.due_date}</td>
                    <td>{tx.payment_date || '—'}</td>
                    <td>{tx.payment_delay != null ? tx.payment_delay : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

export default BuyerLookupPage
