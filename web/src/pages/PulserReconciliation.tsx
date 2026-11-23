import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Badge, Button, Card, ErrorBanner, Modal, PageHeader } from '../components/ui'
import type { PulserReconSummary, TransactionItem } from '../types'

export default function PulserReconciliation() {
  const { can } = useAuth()
  const [summary, setSummary] = useState<PulserReconSummary | null>(null)
  const [transactions, setTransactions] = useState<TransactionItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedTx, setSelectedTx] = useState<TransactionItem | null>(null)
  const [investigationStatus, setInvestigationStatus] = useState('UNDER_REVIEW')
  const [investigationNotes, setInvestigationNotes] = useState('')
  const [saving, setSaving] = useState(false)

  const load = () => {
    setLoading(true)
    Promise.all([
      api.get<PulserReconSummary>('/reconciliation/pulser'),
      api.get<TransactionItem[]>('/transactions?limit=100'),
    ])
      .then(([s, txs]) => {
        setSummary(s)
        setTransactions(txs)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load pulser data'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const openInvestigate = (tx: TransactionItem) => {
    setSelectedTx(tx)
    setInvestigationStatus(tx.investigation_status || 'UNDER_REVIEW')
    setInvestigationNotes(tx.investigation_notes || '')
  }

  const handleSaveInvestigation = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedTx) return
    setSaving(true)
    try {
      await api.patch(`/transactions/${selectedTx.id}/investigate`, {
        investigation_status: investigationStatus,
        investigation_notes: investigationNotes,
      })
      setSelectedTx(null)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update investigation')
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <PageHeader
        title="Fuel Dispenser & Independent Pulser Reconciliation"
        subtitle="Hardware cross-verification between Dispenser CPU volume and dedicated Optical Pulser (0.490 L Threshold Engine)"
        action={<Button onClick={load} variant="secondary">↻ Refresh Metrics</Button>}
      />
      {error && <ErrorBanner message={error} />}

      {/* KPI Cards */}
      <div className="metric-grid" style={{ marginBottom: '16px' }}>
        <Card className="metric-card tone-blue">
          <span className="metric-label">CPU Volume Audited</span>
          <strong className="metric-value">{summary?.total_cpu_volume_l.toLocaleString() ?? 0} L</strong>
          <span className="metric-foot">Reported by Dispenser CPUs</span>
        </Card>
        <Card className="metric-card tone-green">
          <span className="metric-label">Pulser Volume Verified</span>
          <strong className="metric-value">{summary?.total_pulser_volume_l.toLocaleString() ?? 0} L</strong>
          <span className="metric-foot">Independent optical sensor counts</span>
        </Card>
        <Card className={`metric-card ${summary && summary.discrepancy_incidents > 0 ? 'tone-amber' : 'tone-slate'}`}>
          <span className="metric-label">Discrepancy Incidents</span>
          <strong className="metric-value">{summary?.discrepancy_incidents ?? 0}</strong>
          <span className="metric-foot">Exceeded 0.490 L threshold</span>
        </Card>
        <Card className="metric-card tone-purple">
          <span className="metric-label">Compliance Rate</span>
          <strong className="metric-value">{summary?.compliance_rate_percent ?? 100}%</strong>
          <span className="metric-foot">Acceptable forecourt variance</span>
        </Card>
      </div>

      <Card>
        <h3 style={{ marginBottom: '12px' }}>Forecourt Dispensing & Audit Verification Records</h3>
        <div style={{ overflowX: 'auto' }}>
          <table className="table" style={{ width: '100%', fontSize: '13px' }}>
            <thead>
              <tr>
                <th>Reference</th>
                <th>Station / Pump</th>
                <th>CPU Volume</th>
                <th>Pulser Volume</th>
                <th>Delta (ΔV)</th>
                <th>Status</th>
                <th>Investigation</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((t) => {
                const isOverThreshold = t.volume_difference >= 0.490
                return (
                  <tr key={t.id} style={{ background: isOverThreshold ? 'rgba(214, 69, 80, 0.05)' : undefined }}>
                    <td><code>{t.transaction_ref}</code></td>
                    <td>{t.dispenser_code} (N#{t.nozzle_number})<br /><small style={{ color: 'var(--muted)' }}>{t.station_name}</small></td>
                    <td><strong>{t.dispenser_cpu_volume.toFixed(3)} L</strong></td>
                    <td><strong>{t.independent_pulser_volume.toFixed(3)} L</strong></td>
                    <td style={{ color: isOverThreshold ? 'var(--danger)' : 'var(--text)', fontWeight: 700 }}>
                      {t.volume_difference.toFixed(3)} L
                    </td>
                    <td>
                      <Badge tone={isOverThreshold ? 'danger' : 'success'}>
                        {isOverThreshold ? '⚠ ≥0.49L ANOMALY' : '✓ NORMAL'}
                      </Badge>
                    </td>
                    <td>
                      <Badge tone={t.investigation_status === 'RESOLVED' ? 'success' : t.investigation_status === 'UNDER_REVIEW' ? 'warning' : 'neutral'}>
                        {t.investigation_status}
                      </Badge>
                    </td>
                    <td>
                      {can('transactions', 'view') && (
                        <Button
                          variant={isOverThreshold ? 'danger' : 'secondary'}
                          style={{ padding: '4px 8px', fontSize: '11px' }}
                          onClick={() => openInvestigate(t)}
                        >
                          {isOverThreshold ? 'Investigate' : 'Review'}
                        </Button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {selectedTx && (
        <Modal title={`Audit Review — ${selectedTx.transaction_ref}`} onClose={() => setSelectedTx(null)}>
          <form onSubmit={handleSaveInvestigation} style={{ display: 'grid', gap: '14px' }}>
            <div style={{ background: 'var(--surface-2)', padding: '12px', borderRadius: '8px', fontSize: '12px', display: 'grid', gap: '6px' }}>
              <div>Dispenser: <strong>{selectedTx.dispenser_code}</strong> · Nozzle: #{selectedTx.nozzle_number} ({selectedTx.product_code})</div>
              <div>Station: <strong>{selectedTx.station_name}</strong></div>
              <div>CPU Volume: <strong>{selectedTx.dispenser_cpu_volume} L</strong> · Pulser Volume: <strong>{selectedTx.independent_pulser_volume} L</strong></div>
              <div>Raw Optical Pulse Count: <strong>{selectedTx.raw_pulse_count} pulses</strong></div>
              <div>Measurement Difference (ΔV): <strong style={{ color: selectedTx.volume_difference >= 0.49 ? 'var(--danger)' : 'var(--text)' }}>{selectedTx.volume_difference} L</strong></div>
            </div>

            <label className="field">
              <span>Investigation Status</span>
              <select value={investigationStatus} onChange={(e) => setInvestigationStatus(e.target.value)}>
                <option value="NORMAL">Normal</option>
                <option value="UNDER_REVIEW">Under Review / Active Inspection</option>
                <option value="CONFIRMED_INCIDENT">Confirmed Incident / Fuel Diversion</option>
                <option value="RESOLVED">False Alarm / Resolved / Recalibrated</option>
              </select>
            </label>

            <label className="field">
              <span>Investigation Findings & Audit Comments</span>
              <textarea
                rows={3}
                value={investigationNotes}
                onChange={(e) => setInvestigationNotes(e.target.value)}
                placeholder="Enter physical technician notes, calibration check results, or closure reason..."
              />
            </label>

            <Button type="submit" disabled={saving}>
              {saving ? 'Saving...' : 'Commit Investigation Audit Record'}
            </Button>
          </form>
        </Modal>
      )}
    </>
  )
}
