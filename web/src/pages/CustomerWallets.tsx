import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Badge, Button, Card, ErrorBanner, Input, Modal, PageHeader } from '../components/ui'
import type { CustomerItem } from '../types'

export default function CustomerWallets() {
  const { can } = useAuth()
  const [customers, setCustomers] = useState<CustomerItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [creating, setCreating] = useState(false)
  const [fundingCustomer, setFundingCustomer] = useState<CustomerItem | null>(null)
  const [fundAmount, setFundAmount] = useState('25000')
  const [fundReference, setFundReference] = useState('')

  const [form, setForm] = useState({
    full_name: '',
    phone: '',
    email: '',
    category: 'CORPORATE',
    card_uid: '',
  })

  const load = () => {
    setLoading(true)
    api.get<CustomerItem[]>('/customers')
      .then(setCustomers)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load customers'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.post('/customers', form)
      setCreating(false)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to register customer')
    }
  }

  const handleFund = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!fundingCustomer) return
    try {
      await api.post(`/customers/wallets/${fundingCustomer.id}/fund`, {
        amount: parseFloat(fundAmount),
        payment_reference: fundReference,
      })
      setFundingCustomer(null)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Wallet funding failed')
    }
  }

  const toggleCardBlock = async (cardId: string) => {
    try {
      await api.post(`/customers/rfid-cards/${cardId}/toggle-block`)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Card status update failed')
    }
  }

  return (
    <>
      <PageHeader
        title="Special Customer & RFID Wallet Management"
        subtitle="Exclusive registered account wallets, cryptographic card pairing and atomic fuel reservation holds"
        action={
          can('customers', 'create') && <Button onClick={() => setCreating(true)}>+ Register Special Customer</Button>
        }
      />
      {error && <ErrorBanner message={error} />}

      <div style={{ background: 'rgba(14, 165, 164, 0.08)', border: '1px solid var(--border)', padding: '12px 16px', borderRadius: '8px', marginBottom: '16px', fontSize: '13px' }}>
        <strong>Forecourt RFID Policy (Section 8 Compliant):</strong> RFID tap dispensing is restricted to registered special customers. An unregistered card or a card without a verified mobile purchase order hold will never release fuel at any nozzle.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '16px' }}>
        {customers.map((c) => (
          <Card key={c.id}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
              <div>
                <strong style={{ fontSize: '16px' }}>{c.full_name}</strong>
                <div style={{ fontSize: '12px', color: 'var(--muted)' }}>{c.phone} {c.email && `· ${c.email}`}</div>
              </div>
              <Badge tone={c.category === 'CORPORATE' ? 'info' : 'warning'}>{c.category}</Badge>
            </div>

            {/* Wallet Balance Display */}
            <div style={{ background: 'var(--surface-2)', padding: '12px', borderRadius: '8px', margin: '10px 0', display: 'grid', gap: '6px', fontSize: '13px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Wallet Total Balance:</span>
                <strong style={{ color: 'var(--primary)', fontSize: '15px' }}>₦{c.wallet?.balance.toLocaleString() ?? 0}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: 'var(--muted)' }}>
                <span>Active Reservation Hold:</span>
                <span>₦{c.wallet?.reserved.toLocaleString() ?? 0}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', borderTop: '1px solid var(--border)', paddingTop: '4px' }}>
                <span>Available to Spend:</span>
                <strong style={{ color: 'var(--success)' }}>₦{c.wallet?.available.toLocaleString() ?? 0}</strong>
              </div>
            </div>

            {/* RFID Cards */}
            <div style={{ marginBottom: '12px' }}>
              <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--muted)', marginBottom: '6px' }}>
                PAIRED RFID CARDS ({c.cards.length})
              </div>
              {c.cards.map((card) => (
                <div key={card.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--surface)', padding: '6px 10px', borderRadius: '6px', border: '1px solid var(--border)', marginBottom: '4px', fontSize: '12px' }}>
                  <span>UID: <code>{card.card_uid}</code></span>
                  <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                    <Badge tone={card.is_blocked ? 'danger' : 'success'}>
                      {card.is_blocked ? 'BLOCKED' : 'ACTIVE'}
                    </Badge>
                    {can('rfid', 'manage') && (
                      <Button
                        variant={card.is_blocked ? 'secondary' : 'danger'}
                        style={{ padding: '2px 6px', fontSize: '10px' }}
                        onClick={() => toggleCardBlock(card.id)}
                      >
                        {card.is_blocked ? 'Unblock' : 'Block'}
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {can('wallet', 'manage') && (
              <Button
                variant="secondary"
                style={{ width: '100%' }}
                onClick={() => setFundingCustomer(c)}
              >
                + Fund Customer Wallet
              </Button>
            )}
          </Card>
        ))}
      </div>

      {creating && (
        <Modal title="Register Special Customer & Wallet" onClose={() => setCreating(false)}>
          <form onSubmit={handleCreate} style={{ display: 'grid', gap: '12px' }}>
            <Input
              label="Full Name or Organization Name"
              placeholder="e.g. Dangote Cement Fleet Operations"
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              required
            />
            <Input
              label="Phone Number"
              placeholder="+234..."
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              required
            />
            <Input
              label="Email Address"
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
            <label className="field">
              <span>Customer Category</span>
              <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                <option value="CORPORATE">Corporate Fleet</option>
                <option value="VIP">VIP Individual</option>
                <option value="GOVERNMENT">Government Agency</option>
              </select>
            </label>
            <Input
              label="Paired RFID Card UID (Optional)"
              placeholder="e.g. RFID-NG-9812402"
              value={form.card_uid}
              onChange={(e) => setForm({ ...form, card_uid: e.target.value })}
            />
            <Button type="submit">Register Customer & Issue Wallet</Button>
          </form>
        </Modal>
      )}

      {fundingCustomer && (
        <Modal title={`Fund Wallet — ${fundingCustomer.full_name}`} onClose={() => setFundingCustomer(null)}>
          <form onSubmit={handleFund} style={{ display: 'grid', gap: '14px' }}>
            <div style={{ fontSize: '13px' }}>Current Balance: <strong>₦{fundingCustomer.wallet?.balance.toLocaleString()}</strong></div>
            <Input
              label="Deposit Funding Amount (NGN)"
              type="number"
              value={fundAmount}
              onChange={(e) => setFundAmount(e.target.value)}
              required
            />
            <Input
              label="Verified Payment Reference"
              value={fundReference}
              onChange={(e) => setFundReference(e.target.value)}
              required
            />
            <Button type="submit">Deposit Verified Funds</Button>
          </form>
        </Modal>
      )}
    </>
  )
}
