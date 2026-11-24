import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Badge, Button, Card, ErrorBanner, Input, Modal, PageHeader } from '../components/ui'
import type { NozzleItem } from '../types'

export default function Forecourt() {
  const { user } = useAuth()
  const [nozzles, setNozzles] = useState<NozzleItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedNozzle, setSelectedNozzle] = useState<NozzleItem | null>(null)
  const [amount, setAmount] = useState('5000')
  const [paymentChannel, setPaymentChannel] = useState('OPAY_POS')
  const [paymentRef, setPaymentRef] = useState('')
  const [simulateDiscrepancy, setSimulateDiscrepancy] = useState(false)
  const [dispensing, setDispensing] = useState(false)
  const [lastResult, setLastResult] = useState<any>(null)

  const load = () => {
    setLoading(true)
    api.get<NozzleItem[]>('/nozzles')
      .then(setNozzles)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load nozzles'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const triggerDispense = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedNozzle) return
    setError('')
    setDispensing(true)
    setLastResult(null)
    try {
      const res = await api.post<any>('/transactions/simulate-dispense', {
        nozzle_id: selectedNozzle.id,
        requested_amount: parseFloat(amount),
        payment_channel: paymentChannel,
        payment_ref: paymentRef,
        simulate_discrepancy: simulateDiscrepancy,
      })
      setLastResult(res)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Dispensing failed')
    } finally {
      setDispensing(false)
    }
  }

  return (
    <>
      <PageHeader
        title="Forecourt & Dispensing Sandbox"
        subtitle="Real-time pump status, cashless preset trigger, and independent pulser verification"
        action={
          <Button onClick={load} variant="secondary">
            ↻ Refresh Status
          </Button>
        }
      />
      {error && <ErrorBanner message={error} />}

      <div className="forecourt-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
        {nozzles.map((n) => {
          const isOnline = n.fcc?.online ?? false
          return (
            <Card key={n.id} className="forecourt-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <div>
                  <strong style={{ fontSize: '16px' }}>{n.dispenser_code} · Nozzle #{n.number}</strong>
                  <div style={{ color: 'var(--muted)', fontSize: '12px' }}>{n.station_name}</div>
                </div>
                <Badge tone={n.product_code === 'PMS' ? 'info' : n.product_code === 'AGO' ? 'warning' : 'neutral'}>
                  {n.product_code} · ₦{n.price}/L
                </Badge>
              </div>

              <div style={{ background: 'var(--surface-2)', padding: '10px', borderRadius: '8px', fontSize: '12px', display: 'grid', gap: '4px', margin: '10px 0' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>FCC Controller:</span>
                  <span><strong>{n.fcc?.uid ?? 'Unassigned'}</strong> <Badge tone={isOnline ? 'success' : 'danger'}>{isOnline ? 'Online' : 'Offline'}</Badge></span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Connection:</span>
                  <span>{n.fcc?.connection === 'WIFI' ? '📶 Wi-Fi' : '📱 4G SIM'} ({n.fcc?.signal_dbm ?? -70} dBm)</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>OPay POS:</span>
                  <span>{n.pos ? `Terminal #${n.pos.terminal_id}` : 'Unassigned'}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Pulser Calibration:</span>
                  <span>{n.fcc?.cal_factor ?? 100} pulses / Litre</span>
                </div>
              </div>

              <Button
                variant="primary"
                style={{ width: '100%' }}
                onClick={() => {
                  setSelectedNozzle(n)
                  setLastResult(null)
                }}
              >
                ⚡ Authorize & Dispense Fuel
              </Button>
            </Card>
          )
        })}
      </div>

      {selectedNozzle && (
        <Modal title={`Dispense Simulation — ${selectedNozzle.dispenser_code} (Nozzle ${selectedNozzle.number})`} onClose={() => setSelectedNozzle(null)}>
          <form onSubmit={triggerDispense} style={{ display: 'grid', gap: '14px' }}>
            <div style={{ background: 'rgba(15, 111, 189, 0.08)', padding: '10px 14px', borderRadius: '8px', fontSize: '13px' }}>
              <strong>Rule 5 Enforced:</strong> <em>NO VERIFIED PAYMENT, NO FUEL DISPENSING.</em>
              <br />
              Product: <strong>{selectedNozzle.product_code}</strong> at <strong>₦{selectedNozzle.price}/L</strong>.
            </div>

            <Input
              label="Preset Fuel Amount (NGN)"
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              required
            />

            <label className="field">
              <span>Payment Channel (Verified Before Release)</span>
              <select value={paymentChannel} onChange={(e) => setPaymentChannel(e.target.value)}>
                <option value="OPAY_POS">OPay SmartPOS (Card Tap / Chip)</option>
                <option value="BANK_TRANSFER">Instant Bank Transfer (Virtual Account)</option>
                <option value="RFID_WALLET">Special Customer RFID Wallet Card</option>
              </select>
            </label>
            <Input
              label="Verified Payment Reference"
              value={paymentRef}
              onChange={(e) => setPaymentRef(e.target.value)}
              required
            />

            <label style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', background: 'var(--surface-2)', padding: '10px', borderRadius: '8px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={simulateDiscrepancy}
                onChange={(e) => setSimulateDiscrepancy(e.target.checked)}
              />
              <span>
                <strong>Simulate Pulser Discrepancy (≥0.49L Anomaly)</strong>
                <br />
                <small style={{ color: 'var(--muted)' }}>Causes independent pulser to register less fuel than CPU to test automated alert generation.</small>
              </span>
            </label>

            <Button type="submit" disabled={dispensing}>
              {dispensing ? 'Verifying Payment & Dispensing…' : 'Confirm Payment & Trigger Dispense'}
            </Button>

            {lastResult && (
              <div style={{ marginTop: '12px', padding: '12px', borderRadius: '8px', background: lastResult.discrepancy_alert ? 'rgba(214, 69, 80, 0.12)' : 'rgba(22, 146, 91, 0.12)', border: `1px solid ${lastResult.discrepancy_alert ? 'var(--danger)' : 'var(--success)'}` }}>
                <strong style={{ color: lastResult.discrepancy_alert ? 'var(--danger)' : 'var(--success)', display: 'block', marginBottom: '6px' }}>
                  {lastResult.discrepancy_alert ? '⚠ CRITICAL DISCREPANCY DETECTED' : '✓ Normal Dispensing Completed'}
                </strong>
                <div style={{ fontSize: '12px', display: 'grid', gap: '4px' }}>
                  <div>Transaction Ref: <code>{lastResult.transaction_ref}</code></div>
                  <div>Dispenser CPU Volume: <strong>{lastResult.cpu_volume} L</strong></div>
                  <div>Independent Pulser Volume: <strong>{lastResult.pulser_volume} L</strong></div>
                  <div>Measurement Difference (ΔV): <strong>{lastResult.difference} L</strong></div>
                  <div>Total Billed: <strong>₦{lastResult.total_amount_billed.toLocaleString()}</strong></div>
                  {lastResult.discrepancy_alert && (
                    <div style={{ color: 'var(--danger)', marginTop: '4px' }}>
                      Difference of {lastResult.difference} L exceeds the <strong>0.490 L threshold</strong>. Incident logged and flagged for manager investigation.
                    </div>
                  )}
                </div>
              </div>
            )}
          </form>
        </Modal>
      )}
    </>
  )
}
