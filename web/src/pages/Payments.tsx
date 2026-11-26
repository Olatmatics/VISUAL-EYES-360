import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Badge, Button, Card, ErrorBanner, Input, Modal, PageHeader } from '../components/ui'
import type { NozzleItem, PaymentRecordItem, POSTerminalItem, Station } from '../types'

export default function Payments() {
  const { can } = useAuth()
  const [terminals, setTerminals] = useState<POSTerminalItem[]>([])
  const [payments, setPayments] = useState<PaymentRecordItem[]>([])
  const [stations, setStations] = useState<Station[]>([])
  const [nozzles, setNozzles] = useState<NozzleItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [registering, setRegistering] = useState(false)
  const [simulating, setSimulating] = useState(false)
  const [termForm, setTermForm] = useState({
    terminal_id: '',
    serial_number: '',
    provider: 'OPAY',
    station_id: '',
    nozzle_id: '',
  })
  const [simForm, setSimForm] = useState({
    amount: '10000',
    payment_method: 'CARD_POS',
  })
  const [simResult, setSimResult] = useState<any>(null)

  const load = () => {
    setLoading(true)
    Promise.all([
      api.get<POSTerminalItem[]>('/payments/terminals'),
      api.get<PaymentRecordItem[]>('/payments/records'),
      api.get<Station[]>('/stations'),
      api.get<NozzleItem[]>('/nozzles'),
    ])
      .then(([t, p, s, n]) => {
        setTerminals(t)
        setPayments(p)
        setStations(s)
        setNozzles(n)
        if (s.length > 0 && !termForm.station_id) {
          setTermForm((prev) => ({ ...prev, station_id: s[0].id }))
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load payments'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.post('/payments/terminals', termForm)
      setRegistering(false)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to register terminal')
    }
  }

  const handleSimulateOPay = async (e: React.FormEvent) => {
    e.preventDefault()
    setSimResult(null)
    try {
      const res = await api.post('/payments/simulate-opay-checkout', {
        amount: parseFloat(simForm.amount),
        payment_method: simForm.payment_method,
      })
      setSimResult(res)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Payment simulation failed')
    }
  }

  return (
    <>
      <PageHeader
        title="POS Terminals & Cashless Payment Management"
        subtitle="OPay merchant POS terminal assignment, verified bank transfers and cashless authorization gateway"
        action={
          <div style={{ display: 'flex', gap: '8px' }}>
            <Button onClick={() => { setSimulating(true); setSimResult(null) }} variant="primary">
              💳 OPay Sandbox (Development)
            </Button>
            {can('pos', 'create') && <Button onClick={() => setRegistering(true)}>+ Register POS Terminal</Button>}
            <Button onClick={load} variant="secondary">↻</Button>
          </div>
        }
      />
      {error && <ErrorBanner message={error} />}

      <div style={{ background: 'rgba(22, 146, 91, 0.08)', border: '1px solid var(--border)', padding: '12px 16px', borderRadius: '8px', marginBottom: '16px', fontSize: '13px' }}>
        <strong>Payment Authorization Rule:</strong> <em>NO VERIFIED PAYMENT, NO FUEL DISPENSING.</em> Live credentials and callback verification must be configured before any production transaction can be authorized.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        {terminals.map((t) => (
          <Card key={t.id}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
              <div>
                <strong style={{ fontSize: '15px' }}>Terminal #{t.terminal_id}</strong>
                <div style={{ fontSize: '12px', color: 'var(--muted)' }}>{t.station_name}</div>
              </div>
              <Badge tone="success">{t.provider}</Badge>
            </div>
            <div style={{ background: 'var(--surface-2)', padding: '10px', borderRadius: '8px', fontSize: '12px', display: 'grid', gap: '4px' }}>
              <div>Hardware S/N: <code>{t.serial_number}</code></div>
              <div>Assigned Nozzle: <strong>{t.dispenser_code ? `${t.dispenser_code} (Nozzle #${t.nozzle_number})` : 'Unassigned'}</strong></div>
              <div>Status: <Badge tone={t.is_active ? 'success' : 'neutral'}>{t.is_active ? 'Active & Paired' : 'Inactive'}</Badge></div>
            </div>
          </Card>
        ))}
      </div>

      <Card>
        <h3 style={{ marginBottom: '12px' }}>Verified Payment Ledger</h3>
        <div style={{ overflowX: 'auto' }}>
          <table className="table" style={{ width: '100%', fontSize: '13px' }}>
            <thead>
              <tr>
                <th>Reference</th>
                <th>Provider</th>
                <th>Method</th>
                <th>Amount</th>
                <th>Currency</th>
                <th>Status</th>
                <th>Date & Time</th>
              </tr>
            </thead>
            <tbody>
              {payments.map((p) => (
                <tr key={p.id}>
                  <td><code>{p.reference}</code></td>
                  <td><strong>{p.provider}</strong></td>
                  <td>{p.payment_method.replace('_', ' ')}</td>
                  <td><strong>₦{p.amount.toLocaleString()}</strong></td>
                  <td>{p.currency}</td>
                  <td>
                    <Badge
                      tone={
                        p.status === 'VERIFIED'
                          ? 'success'
                          : p.status === 'FAILED' || p.status === 'REFUNDED'
                            ? 'danger'
                            : 'warning'
                      }
                    >
                      {p.status === 'VERIFIED' ? '✓ ' : ''}{p.status}
                    </Badge>
                  </td>
                  <td>{new Date(p.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {registering && (
        <Modal title="Register OPay SmartPOS Terminal" onClose={() => setRegistering(false)}>
          <form onSubmit={handleRegister} style={{ display: 'grid', gap: '12px' }}>
            <label className="field">
              <span>Station Assignment</span>
              <select value={termForm.station_id} onChange={(e) => setTermForm({ ...termForm, station_id: e.target.value })} required>
                {stations.map((s) => (
                  <option key={s.id} value={s.id}>{s.name} ({s.code})</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Assign to Nozzle (required for FCC INIT 5000)</span>
              <select value={termForm.nozzle_id} onChange={(e) => setTermForm({ ...termForm, nozzle_id: e.target.value })}>
                <option value="">Unassigned — do this before bench testing</option>
                {nozzles
                  .filter((n) => !termForm.station_id || n.station_id === termForm.station_id)
                  .map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.dispenser_code} · Nozzle {n.number} · ₦{n.price}/L
                    </option>
                  ))}
              </select>
            </label>
            <Input
              label="Terminal ID"
              placeholder="e.g. OPAY-POS-003"
              value={termForm.terminal_id}
              onChange={(e) => setTermForm({ ...termForm, terminal_id: e.target.value })}
              required
            />
            <Input
              label="Hardware Serial Number"
              placeholder="e.g. SN-8821039"
              value={termForm.serial_number}
              onChange={(e) => setTermForm({ ...termForm, serial_number: e.target.value })}
              required
            />
            <Button type="submit">Register Terminal</Button>
          </form>
        </Modal>
      )}

      {simulating && (
        <Modal title="OPay Gateway Verification Simulation" onClose={() => setSimulating(false)}>
          <form onSubmit={handleSimulateOPay} style={{ display: 'grid', gap: '12px' }}>
            <Input
              label="Transaction Amount (NGN)"
              type="number"
              value={simForm.amount}
              onChange={(e) => setSimForm({ ...simForm, amount: e.target.value })}
              required
            />
            <label className="field">
              <span>Customer Payment Method</span>
              <select value={simForm.payment_method} onChange={(e) => setSimForm({ ...simForm, payment_method: e.target.value })}>
                <option value="CARD_POS">OPay Debit Card Tap / Insert</option>
                <option value="BANK_TRANSFER">Bank Transfer via Virtual Account</option>
              </select>
            </label>
            <Button type="submit">Create Sandbox Payment Reference</Button>

            {simResult && (
              <div style={{ marginTop: '12px', padding: '12px', borderRadius: '8px', background: 'rgba(22, 146, 91, 0.12)', border: '1px solid var(--success)', fontSize: '13px' }}>
                <strong style={{ color: 'var(--warning)' }}>DEVELOPMENT SANDBOX — NOT VERIFIED</strong>
                <div style={{ marginTop: '4px' }}>Reference: <code>{simResult.payment_reference}</code></div>
                <div>Dispensing Authorized: <strong>NO</strong></div>
                <small style={{ color: 'var(--muted)', display: 'block', marginTop: '4px' }}>
                  This reference must not be used as real payment proof or to release fuel.
                </small>
              </div>
            )}
          </form>
        </Modal>
      )}
    </>
  )
}
