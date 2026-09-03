import { useState } from 'react'
import { api, handleAuthError } from '../api'

function UploadPage() {
  const [file, setFile] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  const [buyers, setBuyers] = useState([])
  const [modelInfo, setModelInfo] = useState(null)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const handleFileChange = (e) => {
    setFile(e.target.files?.[0] ?? null)
    setError('')
    setSuccess('')
  }

  const handleUpload = async () => {
    if (!file) {
      setError('Please select a CSV file.')
      return
    }
    setIsUploading(true)
    setError('')
    setSuccess('')
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await api.post('/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setBuyers(res.data)
      const modelRes = await api.get('/model/info')
      setModelInfo(modelRes.data)
      setSuccess(
        `Loaded ${res.data.length} buyers. Model accuracy: ${
          modelRes.data.accuracy_pct != null ? `${modelRes.data.accuracy_pct}%` : 'n/a'
        }.`,
      )
    } catch (err) {
      if (handleAuthError(err)) return
      setError(err.response?.data?.detail || 'Failed to upload CSV.')
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div>
      <h2 className="page-title">Upload Invoice Transactions</h2>
      <p className="page-subtitle">
        Upload a CSV to recompute buyer reliability scores and retrain the logistic regression model.
        Required columns: invoice_id, buyer_name, invoice_amount, issue_date, due_date, payment_date.
      </p>
      <div className="upload-panel">
        <input type="file" accept=".csv" onChange={handleFileChange} />
        <button className="primary-button" onClick={handleUpload} disabled={isUploading}>
          {isUploading ? 'Processing…' : 'Upload & Analyze'}
        </button>
      </div>
      {error && <div className="error-banner">{error}</div>}
      {success && <div className="success-banner">{success}</div>}
      {modelInfo?.loaded && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>Trained Model</h3>
          <p className="muted-text">
            {modelInfo.model_type} · accuracy {modelInfo.accuracy_pct}% · samples {modelInfo.n_samples}
          </p>
        </div>
      )}
      {buyers.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>Per-buyer reliability summary</h3>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Buyer</th>
                  <th>Avg Delay (days)</th>
                  <th>Late %</th>
                  <th>Reliability Score</th>
                  <th>Predicted Delay Prob.</th>
                  <th>Risk</th>
                </tr>
              </thead>
              <tbody>
                {buyers.map((b) => (
                  <tr key={b.buyer_name}>
                    <td>{b.buyer_name}</td>
                    <td>{b.average_delay.toFixed(1)}</td>
                    <td>{b.late_payment_percentage.toFixed(1)}%</td>
                    <td>{b.reliability_score.toFixed(1)}</td>
                    <td>
                      {b.predicted_delay_probability != null
                        ? `${(b.predicted_delay_probability * 100).toFixed(1)}%`
                        : '—'}
                    </td>
                    <td>{b.risk_classification}</td>
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

export default UploadPage
