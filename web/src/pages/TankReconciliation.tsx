import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Badge, Button, Card, ErrorBanner, Modal, PageHeader } from '../components/ui'
import type { TankItem, TankReconciliationItem } from '../types'

export default function TankReconciliation() {
  const { can } = useAuth()
  const [records, setRecords] = useState<TankReconciliationItem[]>([])
  const [tanks, setTanks] = useState<TankItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [running, setRunning] = useState(false)
  const [selectedTankId, setSelectedTankId] = useState('')

  const load = () => {
    setLoading(true)
    Promise.all([
      api.get<TankReconciliationItem[]>('/reconciliation/tanks'),
      api.get<TankItem[]>('/tanks'),
    ])
      .then(([r, t]) => {
        setRecords(r)
        setTanks(t)
        if (t.length > 0 && !selectedTankId) {
          setSelectedTankId(t[0].id)
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load reconciliation records'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const handleRunRecon = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await api.post('/reconciliation/tanks/run', { tank_id: selectedTankId })
      setRunning(false)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reconciliation run failed')
    }
  }

  return (
    <>
      <PageHeader
        title="Fuel Tank Inventory Reconciliation"
        subtitle="Expected Closing Stock = Opening Stock + Deliveries − Sales vs Actual ATG Physical Gauge"
        action={
          can('tank_reconciliation', 'manage') && (
            <Button onClick={() => setRunning(true)}>⚡ Run Shift Reconciliation</Button>
          )
        }
      />
      {error && <ErrorBanner message={error} />}

      <div style={{ background: 'var(--surface)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border)', marginBottom: '16px' }}>
        <h4 style={{ margin: '0 0 8px', fontSize: '14px' }}>Reconciliation Formula (Section 12 Compliant)</h4>
        <div style={{ fontSize: '13px', color: 'var(--muted)', display: 'grid', gap: '4px' }}>
          <div><code>Expected Closing Stock = Opening Physical Stock + Decanted Deliveries − Total CPU Dispensed Volume</code></div>
          <div><code>Tank Variance = Actual Physical ATG Closing Stock − Expected Closing Stock</code></div>
        </div>
      </div>

      <div style={{ display: 'grid', gap: '12px' }}>
        {records.map((r) => {
          const isCritical = r.status === 'CRITICAL_INVESTIGATION'
          return (
            <Card key={r.id}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                <div>
                  <strong style={{ fontSize: '16px' }}>{r.tank_code} · {r.station_name}</strong>
                  <div style={{ fontSize: '12px', color: 'var(--muted)' }}>Shift Date: {r.shift_date} · Recorded: {new Date(r.recorded_at).toLocaleTimeString()}</div>
                </div>
                <Badge tone={isCritical ? 'danger' : r.status === 'WARNING' ? 'warning' : 'success'}>
                  {r.status}
                </Badge>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '10px', background: 'var(--surface-2)', padding: '12px', borderRadius: '8px', fontSize: '12px' }}>
                <div>
                  <span style={{ color: 'var(--muted)' }}>Opening Stock:</span>
                  <div><strong>{r.opening_stock_l.toLocaleString()} L</strong></div>
                </div>
                <div>
                  <span style={{ color: 'var(--muted)' }}>Deliveries:</span>
                  <div><strong>+{r.deliveries_l.toLocaleString()} L</strong></div>
                </div>
                <div>
                  <span style={{ color: 'var(--muted)' }}>CPU Sales:</span>
                  <div><strong>−{r.sales_cpu_l.toLocaleString()} L</strong></div>
                </div>
                <div>
                  <span style={{ color: 'var(--muted)' }}>Expected Stock:</span>
                  <div><strong>{r.expected_closing_stock_l.toLocaleString()} L</strong></div>
                </div>
                <div>
                  <span style={{ color: 'var(--muted)' }}>Actual ATG Stock:</span>
                  <div><strong>{r.actual_atg_closing_stock_l.toLocaleString()} L</strong></div>
                </div>
                <div>
                  <span style={{ color: 'var(--muted)' }}>Variance (Δ):</span>
                  <div style={{ color: isCritical ? 'var(--danger)' : 'var(--text)', fontWeight: 700 }}>
                    {r.variance_l > 0 ? `+${r.variance_l}` : r.variance_l} L ({r.variance_percentage}%)
                  </div>
                </div>
              </div>
            </Card>
          )
        })}
      </div>

      {running && (
        <Modal title="Execute Shift Tank Reconciliation" onClose={() => setRunning(false)}>
          <form onSubmit={handleRunRecon} style={{ display: 'grid', gap: '14px' }}>
            <label className="field">
              <span>Select Storage Tank</span>
              <select value={selectedTankId} onChange={(e) => setSelectedTankId(e.target.value)} required>
                {tanks.map((t) => (
                  <option key={t.id} value={t.id}>{t.code} — {t.station_name} ({t.product_code})</option>
                ))}
              </select>
            </label>
            <p style={{ fontSize: '12px', color: 'var(--muted)' }}>
              Executing reconciliation automatically fetches the latest magnetostrictive probe ATG closing volume, aggregates total dispenser sales since previous shift, and calculates variance against acceptable forecourt tolerances.
            </p>
            <Button type="submit">Compute & Record Reconciliation</Button>
          </form>
        </Modal>
      )}
    </>
  )
}
