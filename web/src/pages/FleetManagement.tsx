import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Badge, Button, Card, ErrorBanner, Input, Modal, PageHeader } from '../components/ui'
import type { FleetItem } from '../types'

export default function FleetManagement() {
  const { can } = useAuth()
  const [fleets, setFleets] = useState<FleetItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({
    name: '',
    code: '',
    organization: '',
    spending_limit: '1500000',
  })

  const load = () => {
    setLoading(true)
    api.get<FleetItem[]>('/customers/fleets')
      .then(setFleets)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load fleets'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.post('/customers/fleets', form)
      setCreating(false)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create fleet')
    }
  }

  return (
    <>
      <PageHeader
        title="Fleet & Commercial Vehicle Management"
        subtitle="Manage fleet organizations, commercial vehicle quotas, assigned drivers and fuel consumption"
        action={
          can('fleet', 'create') && <Button onClick={() => setCreating(true)}>+ Register Commercial Fleet</Button>
        }
      />
      {error && <ErrorBanner message={error} />}

      <div style={{ display: 'grid', gap: '16px' }}>
        {fleets.map((f) => (
          <Card key={f.id}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '18px' }}>{f.name} ({f.code})</h3>
                <small style={{ color: 'var(--muted)' }}>Organization: <strong>{f.organization}</strong></small>
              </div>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <span style={{ fontSize: '12px' }}>Quota Limit: <strong>₦{f.spending_limit.toLocaleString()}</strong></span>
                <Badge tone="success">{f.status}</Badge>
              </div>
            </div>

            <div style={{ background: 'var(--surface-2)', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '8px', color: 'var(--muted)' }}>
                REGISTERED FLEET VEHICLES ({f.vehicles.length})
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '10px' }}>
                {f.vehicles.map((v) => (
                  <div key={v.id} style={{ background: 'var(--surface)', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '12px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <strong>{v.plate_number}</strong>
                      <Badge tone="neutral">{v.vehicle_type}</Badge>
                    </div>
                    <div style={{ color: 'var(--muted)', display: 'grid', gap: '2px' }}>
                      <div>Driver: <strong>{v.driver_name}</strong></div>
                      <div>Product: <strong>{v.fuel_type}</strong> · Spending Limit: ₦{v.spending_limit.toLocaleString()}</div>
                      <div>Odometer: {v.odometer_km.toLocaleString()} km</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        ))}
      </div>

      {creating && (
        <Modal title="Register Commercial Fleet" onClose={() => setCreating(false)}>
          <form onSubmit={handleCreate} style={{ display: 'grid', gap: '12px' }}>
            <Input
              label="Fleet Name"
              placeholder="e.g. Dangote Logistics Abuja Hub"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
            <Input
              label="Fleet Code"
              placeholder="e.g. FLT-DNG-02"
              value={form.code}
              onChange={(e) => setForm({ ...form, code: e.target.value })}
              required
            />
            <Input
              label="Organization / Company"
              placeholder="e.g. Dangote Group"
              value={form.organization}
              onChange={(e) => setForm({ ...form, organization: e.target.value })}
              required
            />
            <Input
              label="Monthly Fuel Allowance Quota (NGN)"
              type="number"
              value={form.spending_limit}
              onChange={(e) => setForm({ ...form, spending_limit: e.target.value })}
              required
            />
            <Button type="submit">Create Fleet Account</Button>
          </form>
        </Modal>
      )}
    </>
  )
}
