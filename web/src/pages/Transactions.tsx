import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Badge, Button, Card, ErrorBanner, Modal, PageHeader } from '../components/ui'
import type { TransactionItem } from '../types'

export default function Transactions() {
  const { user } = useAuth()
  const [transactions, setTransactions] = useState<TransactionItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedTx, setSelectedTx] = useState<TransactionItem | null>(null)
  const [filterDiscrepancy, setFilterDiscrepancy] = useState(false)

  const load = () => {
    setLoading(true)
    api.get<TransactionItem[]>(`/transactions?limit=100&discrepancy_only=${filterDiscrepancy}`)
      .then(setTransactions)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load transactions'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [filterDiscrepancy])

  return (
    <>
      <PageHeader
        title="Fuel Transactions & Dual-Measurement Journal"
        subtitle="Verified dispensing records with CPU volume, independent pulser volume and payment linkage"
        action={
          <div style={{ display: 'flex', gap: '8px' }}>
            <Button
              variant={filterDiscrepancy ? 'danger' : 'secondary'}
              onClick={() => setFilterDiscrepancy(!filterDiscrepancy)}
            >
              {filterDiscrepancy ? 'Showing Only ≥0.49L Discrepancies' : 'Filter Anomaly Discrepancies'}
            </Button>
            <Button onClick={load} variant="secondary">↻ Refresh</Button>
          </div>
        }
      />
      {error && <ErrorBanner message={error} />}

      <Card>
        <div style={{ overflowX: 'auto' }}>
          <table className="table" style={{ width: '100%', fontSize: '13px' }}>
            <thead>
              <tr>
                <th>Reference</th>
                <th>Time</th>
                <th>Station / Pump</th>
                <th>Product</th>
                <th>Billed Amount</th>
                <th>CPU Volume</th>
                <th>Pulser Volume</th>
                <th>Delta</th>
                <th>Payment</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((t) => (
                <tr key={t.id} style={{ background: t.discrepancy_alert ? 'rgba(214, 69, 80, 0.05)' : undefined }}>
                  <td><code>{t.transaction_ref}</code></td>
                  <td>{new Date(t.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</td>
                  <td>{t.station_name}<br /><small style={{ color: 'var(--muted)' }}>{t.dispenser_code} · N#{t.nozzle_number}</small></td>
                  <td><strong>{t.product_code}</strong></td>
                  <td><strong>₦{t.total_amount_billed.toLocaleString()}</strong></td>
                  <td>{t.dispenser_cpu_volume.toFixed(3)} L</td>
                  <td>{t.independent_pulser_volume.toFixed(3)} L</td>
                  <td style={{ color: t.discrepancy_alert ? 'var(--danger)' : 'var(--text)', fontWeight: 600 }}>
                    {t.volume_difference.toFixed(3)} L {t.discrepancy_alert && '⚠'}
                  </td>
                  <td><Badge tone="info">{t.payment_channel.replace('_', ' ')}</Badge></td>
                  <td>
                    <Button
                      variant="secondary"
                      style={{ padding: '3px 8px', fontSize: '11px' }}
                      onClick={() => setSelectedTx(t)}
                    >
                      Receipt
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {selectedTx && (
        <Modal title={`Transaction Receipt — ${selectedTx.transaction_ref}`} onClose={() => setSelectedTx(null)}>
          <div style={{ padding: '10px 0', display: 'grid', gap: '12px', fontSize: '13px' }}>
            <div style={{ textAlign: 'center', borderBottom: '1px dashed var(--border)', paddingBottom: '12px' }}>
              <div style={{ fontWeight: 800, fontSize: '16px' }}>VISUAL EYES 360 · FORECOURT RECEIPT</div>
              <div style={{ color: 'var(--muted)' }}>{selectedTx.station_name}</div>
              <small>{new Date(selectedTx.started_at).toLocaleString()}</small>
            </div>

            <div style={{ display: 'grid', gap: '6px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Transaction Ref:</span>
                <code>{selectedTx.transaction_ref}</code>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Dispenser / Nozzle:</span>
                <strong>{selectedTx.dispenser_code} · Nozzle #{selectedTx.nozzle_number}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Fuel Product:</span>
                <strong>{selectedTx.product_code}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Unit Price:</span>
                <strong>₦{selectedTx.unit_price}/L</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Dispenser CPU Volume:</span>
                <strong>{selectedTx.dispenser_cpu_volume} L</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Independent Pulser Volume:</span>
                <strong>{selectedTx.independent_pulser_volume} L</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Measurement Difference:</span>
                <strong style={{ color: selectedTx.discrepancy_alert ? 'var(--danger)' : 'var(--text)' }}>
                  {selectedTx.volume_difference} L {selectedTx.discrepancy_alert && '(≥0.490L Alert)'}
                </strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Payment Channel:</span>
                <strong>{selectedTx.payment_channel}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Payment Reference:</span>
                <code>{selectedTx.payment_ref}</code>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px dashed var(--border)', paddingTop: '8px', fontSize: '16px' }}>
                <strong>TOTAL BILLED:</strong>
                <strong style={{ color: 'var(--primary)' }}>₦{selectedTx.total_amount_billed.toLocaleString()}</strong>
              </div>
            </div>

            <Button onClick={() => setSelectedTx(null)} style={{ marginTop: '10px' }}>Close Receipt</Button>
          </div>
        </Modal>
      )}
    </>
  )
}
