import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Badge, Button, Card, ErrorBanner, Input, Modal, PageHeader } from '../components/ui'
import type { DispenserItem, PumpType, Station } from '../types'

type FormState = {
  station_id: string
  code: string
  name: string
  serial: string
  manufacturer: string
  custom_manufacturer: string
  model: string
  pump_type_id: string
  nozzle_config: 'SINGLE' | 'DOUBLE' | 'OTHER'
  nozzle_count: number
  price_1: string
  price_2: string
  protocol: string
  interface: string
  status: string
}

const emptyForm = (): FormState => ({
  station_id: '', code: '', name: '', serial: '', manufacturer: 'Wayne',
  custom_manufacturer: '', model: 'iGEM 2-Hose', pump_type_id: '',
  nozzle_config: 'DOUBLE', nozzle_count: 2, price_1: '1150', price_2: '890',
  protocol: 'Wayne_Dart', interface: 'RS485_CurrentLoop', status: 'ACTIVE',
})

export default function Dispensers() {
  const { can } = useAuth()
  const [dispensers, setDispensers] = useState<DispenserItem[]>([])
  const [stations, setStations] = useState<Station[]>([])
  const [pumpTypes, setPumpTypes] = useState<PumpType[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [creating, setCreating] = useState(false)
  const [newPumpType, setNewPumpType] = useState({ code: '', name: '', description: '' })
  const [form, setForm] = useState<FormState>(emptyForm())

  const load = () => {
    setLoading(true)
    Promise.all([
      api.get<DispenserItem[]>('/dispensers'),
      api.get<Station[]>('/stations'),
      api.get<PumpType[]>('/pump-types?include_inactive=true').catch(() => [] as PumpType[]),
    ])
      .then(([d, s, p]) => {
        setDispensers(d)
        setStations(s)
        setPumpTypes(p)
        if (s.length > 0 && !form.station_id) setForm((prev) => ({ ...prev, station_id: s[0].id }))
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load dispensers'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    const count = form.nozzle_config === 'SINGLE' ? 1 : form.nozzle_config === 'DOUBLE' ? 2 : form.nozzle_count
    const nozzles = Array.from({ length: count }, (_, i) => ({
      number: i + 1,
      name: `Nozzle ${i + 1}`,
      price: Number(i === 0 ? form.price_1 : form.price_2 || form.price_1),
    }))
    try {
      await api.post('/dispensers', {
        station_id: form.station_id,
        code: form.code.trim(),
        name: form.name.trim() || undefined,
        serial: form.serial.trim() || undefined,
        manufacturer: form.manufacturer,
        custom_manufacturer: form.manufacturer === 'Other' ? form.custom_manufacturer : undefined,
        model: form.model.trim() || undefined,
        pump_type_id: form.pump_type_id || undefined,
        nozzle_config: form.nozzle_config,
        nozzle_count: count,
        nozzles,
        protocol: form.protocol.trim() || undefined,
        interface: form.interface.trim() || undefined,
        status: form.status,
      })
      setCreating(false)
      setForm({ ...emptyForm(), station_id: form.station_id })
      setSuccess(`Dispenser registered with ${count} nozzle${count > 1 ? 's' : ''}.`)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create dispenser')
    }
  }

  const handlePumpType = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await api.post('/pump-types', newPumpType)
      setNewPumpType({ code: '', name: '', description: '' })
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create pump type')
    }
  }

  return (
    <>
      <PageHeader
        title="Dispenser & Pump Management"
        subtitle="Register dispensers, pump types and automatically generated nozzle records"
        action={can('dispensers', 'create') && <Button onClick={() => setCreating(true)}>+ Register Dispenser</Button>}
      />
      {error && <ErrorBanner message={error} />}
      {success && <div className="notice-success">{success}</div>}
      {stations.length === 0 && <ErrorBanner message="Register a station first — a dispenser cannot exist without one." />}

      <Card>
        <h3>Pump Type Management</h3>
        <p className="muted" style={{ fontSize: 13 }}>
          Pump types created here become available in the dispenser registration dropdown.
        </p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
          {pumpTypes.map((p) => <Badge key={p.id} tone={p.is_active ? 'success' : 'neutral'}>{p.name}</Badge>)}
        </div>
        <form onSubmit={handlePumpType} style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Input label="Code" placeholder="e.g. WAYNE_IGEM" value={newPumpType.code}
            onChange={(e) => setNewPumpType({ ...newPumpType, code: e.target.value })} required />
          <Input label="Name" placeholder="e.g. Wayne iGEM" value={newPumpType.name}
            onChange={(e) => setNewPumpType({ ...newPumpType, name: e.target.value })} required />
          <Input label="Description" value={newPumpType.description}
            onChange={(e) => setNewPumpType({ ...newPumpType, description: e.target.value })} />
          <Button type="submit" variant="secondary">+ Add pump type</Button>
        </form>
      </Card>

      <div style={{ display: 'grid', gap: '16px' }}>
        {loading && <div className="empty-state">Loading dispensers…</div>}
        {!loading && dispensers.length === 0 && <div className="empty-state">No dispensers registered yet.</div>}
        {dispensers.map((d) => (
          <Card key={d.id}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '18px' }}>{d.code} · {d.manufacturer} {d.model}</h3>
                <small style={{ color: 'var(--muted)' }}>
                  Station: <strong>{d.station_name}</strong> · Pump type: {d.pump_type_name || '—'} ·
                  Protocol: <code>{d.protocol}</code> · S/N: {d.serial}
                </small>
              </div>
              <Badge tone={d.status === 'ACTIVE' ? 'success' : 'neutral'}>{d.status}</Badge>
            </div>
            <div style={{ background: 'var(--surface-2)', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '8px', color: 'var(--muted)' }}>
                NOZZLES & DEDICATED CONTROLLER CHANNELS ({d.nozzles.length})
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '12px' }}>
                {d.nozzles.map((n) => (
                  <div key={n.id} style={{ background: 'var(--surface)', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <strong>Nozzle #{n.number} · {n.product_code || 'Unassigned product'}</strong>
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
            <label className="field"><span>Assigned Fuel Station</span>
              <select value={form.station_id} onChange={(e) => setForm({ ...form, station_id: e.target.value })} required>
                <option value="">Select station</option>
                {stations.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.code})</option>)}
              </select>
            </label>
            <div className="form-grid">
              <Input label="Dispenser code" placeholder="e.g. DISP-02" value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })} required />
              <Input label="Display name" placeholder="e.g. Pump 1 - Diesel" value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <Input label="Serial number" placeholder="Optional" value={form.serial}
                onChange={(e) => setForm({ ...form, serial: e.target.value })} />
            </div>
            <div className="form-grid">
              <label className="field"><span>Manufacturer / Brand</span>
                <select value={form.manufacturer} onChange={(e) => setForm({ ...form, manufacturer: e.target.value })}>
                  <option value="Wayne">Wayne</option>
                  <option value="Veeder-Root">Veeder-Root</option>
                  <option value="Gilbarco">Gilbarco</option>
                  <option value="Tatsuno">Tatsuno</option>
                  <option value="Tokheim">Tokheim</option>
                  <option value="Bennett">Bennett</option>
                  <option value="Other">Other</option>
                </select>
              </label>
              {form.manufacturer === 'Other' && (
                <Input label="Custom manufacturer" value={form.custom_manufacturer}
                  onChange={(e) => setForm({ ...form, custom_manufacturer: e.target.value })} required />
              )}
              <Input label="Model" value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} />
              <label className="field"><span>Pump type</span>
                <select value={form.pump_type_id} onChange={(e) => setForm({ ...form, pump_type_id: e.target.value })}>
                  <option value="">None / not specified</option>
                  {pumpTypes.filter((p) => p.is_active).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </label>
              <label className="field"><span>Nozzle configuration</span>
                <select value={form.nozzle_config} onChange={(e) => setForm({ ...form, nozzle_config: e.target.value as FormState['nozzle_config'] })}>
                  <option value="SINGLE">Single nozzle</option>
                  <option value="DOUBLE">Double nozzle (2 records created)</option>
                  <option value="OTHER">Other (specify count)</option>
                </select>
              </label>
              {form.nozzle_config === 'OTHER' && (
                <Input label="Number of nozzles" type="number" min={1} max={12} value={form.nozzle_count}
                  onChange={(e) => setForm({ ...form, nozzle_count: Number(e.target.value) })} required />
              )}
              <Input label="Nozzle 1 price (₦/L)" type="number" step="0.01" value={form.price_1}
                onChange={(e) => setForm({ ...form, price_1: e.target.value })} required />
              {(form.nozzle_config === 'DOUBLE' || (form.nozzle_config === 'OTHER' && form.nozzle_count > 1)) && (
                <Input label="Nozzle 2 price (₦/L)" type="number" step="0.01" value={form.price_2}
                  onChange={(e) => setForm({ ...form, price_2: e.target.value })} required />
              )}
              <Input label="Protocol" value={form.protocol} onChange={(e) => setForm({ ...form, protocol: e.target.value })} />
              <Input label="Interface" value={form.interface} onChange={(e) => setForm({ ...form, interface: e.target.value })} />
            </div>
            <Button type="submit">Create Dispenser</Button>
          </form>
        </Modal>
      )}
    </>
  )
}
