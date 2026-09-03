import { useEffect, useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts'
import { api, handleAuthError } from '../api'

const RISK_COLORS = {
  'Low Risk': '#14B8A6',
  'Medium Risk': '#F59E0B',
  'High Risk': '#EF4444',
}

function DashboardPage() {
  const [metrics, setMetrics] = useState(null)
  const [buyers, setBuyers] = useState([])
  const [modelInfo, setModelInfo] = useState(null)
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [mRes, bRes, sRes, modelRes] = await Promise.all([
          api.get('/dashboard'),
          api.get('/buyers'),
          api.get('/stats'),
          api.get('/model/info'),
        ])
        setMetrics(mRes.data)
        setBuyers(bRes.data)
        setStats(sRes.data)
        setModelInfo(modelRes.data)
      } catch (err) {
        if (handleAuthError(err)) return
        setError('Failed to load analytics. Is the backend running on port 8000?')
      } finally {
        setLoading(false)
      }
    }
    fetchAll()
  }, [])

  if (loading) return <div className="muted-text">Loading dashboard…</div>
  if (error) return <div className="error-banner">{error}</div>

  if (!metrics || metrics.total_buyers === 0) {
    return (
      <div className="empty-state">
        <h2 className="page-title">Portfolio Overview</h2>
        <p>No analytics yet. Go to Upload Data and load the sample CSV, or run:</p>
        <code>python3 -m backend.seed</code>
      </div>
    )
  }

  const riskData = metrics.risk_distribution || []
  const worstBuyers = [...buyers]
    .sort((a, b) => a.reliability_score - b.reliability_score)
    .slice(0, 12)

  return (
    <div>
      <h2 className="page-title">Portfolio Overview</h2>
      <p className="page-subtitle">
        Live buyer payment metrics computed from the SQLite database.
      </p>

      <div className="metrics-grid">
        <div className="metric-card">
          <span className="metric-label">Total Buyers</span>
          <span className="metric-value">{metrics.total_buyers}</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Total Transactions</span>
          <span className="metric-value">{metrics.total_transactions}</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Avg Payment Delay</span>
          <span className="metric-value">{metrics.average_payment_delay.toFixed(1)} days</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">High Risk Buyers</span>
          <span className="metric-value">{metrics.high_risk_buyers}</span>
        </div>
      </div>

      {stats && (
        <div className="metrics-grid">
          <div className="metric-card">
            <span className="metric-label">Late Payment Rate</span>
            <span className="metric-value">{stats.late_payment_rate.toFixed(1)}%</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Avg Reliability Score</span>
            <span className="metric-value">{stats.average_reliability_score.toFixed(1)}</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Model Accuracy</span>
            <span className="metric-value">
              {modelInfo?.loaded && modelInfo.accuracy_pct != null
                ? `${modelInfo.accuracy_pct}%`
                : '—'}
            </span>
          </div>
          <div className="metric-card">
               <span className="metric-label">Receivables at Risk</span>
            <span className="metric-value">
              ₹{stats.receivables_at_risk != null
                ? stats.receivables_at_risk.toLocaleString(undefined, { maximumFractionDigits: 0 })
                : '—'}
            </span>
          </div>
        </div>
      )}

      {stats && (
        <p className="muted-text" style={{ marginTop: -8, marginBottom: 16 }}>
                    Total invoice value associated with {metrics.high_risk_buyers} high-risk buyers.
        </p>
      )}

      {modelInfo?.loaded && (
        <div className="card" style={{ marginBottom: 20 }}>
          <h3>Model Performance (held-out test set)</h3>
          <div className="metrics-grid">
            <div className="metric-card">
              <span className="metric-label">Precision</span>
              <span className="metric-value">
                {modelInfo.precision != null ? modelInfo.precision.toFixed(2) : '—'}
              </span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Recall</span>
              <span className="metric-value">
                {modelInfo.recall != null ? modelInfo.recall.toFixed(2) : '—'}
              </span>
            </div>
            <div className="metric-card">
              <span className="metric-label">ROC-AUC</span>
              <span className="metric-value">
                {modelInfo.roc_auc != null ? modelInfo.roc_auc.toFixed(2) : '—'}
              </span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Est. False-Positive Cost</span>
              <span className="metric-value">
                {modelInfo.false_positive_cost_estimate != null
                  ? `₹${modelInfo.false_positive_cost_estimate.toLocaleString()}`
                  : '—'}
              </span>
            </div>
          </div>
          {modelInfo.confusion_matrix && (
            <p className="muted-text" style={{ marginTop: 8, marginBottom: 0 }}>
              Test set confusion matrix — TP: {modelInfo.confusion_matrix.true_positive}, FP:{' '}
              {modelInfo.confusion_matrix.false_positive}, FN:{' '}
              {modelInfo.confusion_matrix.false_negative}, TN:{' '}
              {modelInfo.confusion_matrix.true_negative} (n_test = {modelInfo.n_test})
            </p>
          )}
          {modelInfo.false_positive_cost_assumption && (
            <p className="muted-text" style={{ marginTop: 4, marginBottom: 0 }}>
              {modelInfo.false_positive_cost_assumption}
            </p>
          )}
        </div>
      )}

      {modelInfo?.summary && (
        <p className="muted-text" style={{ marginTop: -4, marginBottom: 16 }}>
          {modelInfo.summary}
        </p>
      )}

      <div className="grid-2">
        <div className="card">
          <h3>Payment Delay Trend</h3>
          {metrics.delay_trend?.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={metrics.delay_trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="label" stroke="#475569" tick={{ fontSize: 11 }} />
                <YAxis stroke="#475569" />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="value"
                  name="Avg delay (days)"
                  stroke="#14B8A6"
                  strokeWidth={2}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="muted-text">No monthly trend data yet.</p>
          )}
        </div>

        <div className="card">
          <h3>Risk Distribution</h3>
          {riskData.some((d) => d.value > 0) ? (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={riskData} dataKey="value" nameKey="name" outerRadius={90} label>
                  {riskData.map((entry) => (
                    <Cell key={entry.name} fill={RISK_COLORS[entry.name] || '#64748b'} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="muted-text">No risk classifications available.</p>
          )}
        </div>
      </div>

      <div className="card" style={{ marginTop: 20 }}>
        <h3>Lowest Reliability Scores</h3>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={worstBuyers}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="buyer_name" hide />
            <YAxis domain={[0, 100]} />
            <Tooltip />
            <Bar
              dataKey="reliability_score"
              name="Reliability score"
              fill="#1F3A8A"
              radius={[6, 6, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
        <p className="muted-text">Showing the 12 lowest-scoring buyers.</p>
      </div>
    </div>
  )
}

export default DashboardPage
