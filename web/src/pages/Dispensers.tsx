import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Badge, Button, Card, ErrorBanner, Input, Modal, PageHeader } from '../components/ui'
import type { DispenserItem, Station } from '../types'

export default function Dispensers() {
  const { can } = useAuth()
  const [dispensers, setDispensers] = useState<DispenserItem[]>([])
  const [stations, setStations] = useState<Station[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({
    station_id: '',
    code: '',
    manufacturer: 'Wayne',
    model: 'iGEM 2-Hose',
    protocol: 'Wayne_Dart',
    interface: 'RS485_CurrentLoop',
  })

  const load = () => {
    setLoading(true)
    Promise.all([
      api.get<DispenserItem[]>('/dispensers'),
      api.get<Station[]>('/stations'),
    ])
      .then(([d, s]) => {
        setDispensers(d)
        setStations(s)
        if (s.length > 0 && !form.station_id) {
          setForm((prev) => ({ ...prev, station_id: s[0].id }))
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load dispensers'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await api.post('/dispensers', form)
      setCreating(false)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create dispenser')
    }
  }

  return (
    <>
      <PageHeader
        title="Dispenser & Pump Management"
        subtitle="Manage Wayne, Gilbarco and Tatsuno dispensers, electronic CPU protocols and nozzles"
        action={
          can('dispensers', 'create') && (
            <Button onClick={() => setCreating(true)}>+ Register Dispenser</Button>
          )
        }
      />
      {error && <ErrorBanner message={error} />}

      <div style={{ display: 'grid', gap: '16px' }}>
        {dispensers.map((d) => (
          <Card key={d.id}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '18px' }}>{d.code} · {d.manufacturer} {d.model}</h3>
                <small style={{ color: 'var(--muted)' }}>
                  Station: <strong>{d.station_name}</strong> · Protocol: <code>{d.protocol}</code> ({d.interface}) · S/N: {d.serial}
                </small>
              </div>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <span style={{ fontSize: '12px', color: 'var(--muted)' }}>Totalizer: <strong>{d.totalizer_l.toLocaleString()} L</strong></span>
                <Badge tone={d.status === 'ACTIVE' ? 'success' : 'neutral'}>{d.status}</Badge>
              </div>
            </div>

            <div style={{ background: 'var(--surface-2)', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '8px', color: 'var(--muted)' }}>
                NOZZLES & DEDICATED CONTROLLER CHANNELS ({d.nozzles.length})
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '12px' }}>
                {d.nozzles.map((n) => (
                  <div key={n.id} style={{ background: 'var(--surface)', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <strong>Nozzle #{n.number} · {n.product_code}</strong>
                      <span style={{ color: 'var(--primary)', fontWeight: 600 }}>₦{n.price}/L</span>
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--muted)', display: 'grid', gap: '2px' }}>
                      <div>Dedicated FCC: <code>{n.fcc_uid ?? 'Pending Assign'}</code></div>
                      <div>POS Terminal: <strong>{n.pos_terminal_id ?? 'None'}</strong></div>
                      <div>Assigned Tank: {n.tank_id ? '✓ Mapped' : '⚠ Unassigned'}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        ))}
      </div>

      {creating && (
        <Modal title="Register Dispenser" onClose={() => setCreating(false)}>
          <form onSubmit={handleCreate} style={{ display: 'grid', gap: '12px' }}>
            <label className="field">
              <span>Assigned Fuel Station</span>
              <select value={form.station_id} onChange={(e) => setForm({ ...form, station_id: e.target.value })} required>
                {stations.map((s) => (
                  <option key={s.id} value={s.id}>{s.name} ({s.code})</option>
                ))}
              </select>
            </label>
            <Input
              label="Dispenser Unit Code"
              placeholder="e.g. DISP-02"
              value={form.code}
              onChange={(e) => setForm({ ...form, code: e.target.value })}
              required
            />
            <label className="field">
              <span>Manufacturer</span>
              <select value={form.manufacturer} onChange={(e) => setForm({ ...form, manufacturer: e.target.value })}>
                <option value="Wayne">Wayne (iGEM / Dart)</option>
                <option value="Gilbarco">Gilbarco (Encore 500S / TwoWire)</option>
                <option value="Tatsuno">Tatsuno (Benc)</option>
              </select>
            </label>
            <Input
              label="Model"
              placeholder="e.g. iGEM 2-Hose"
              value={form.model}
              onChange={(e) => setForm({ ...form, model: e.target.value })}
            />
            <Button type="submit">Create Dispenser</Button>
          </form>
        </Modal>
      )}
    </>
  )
}
