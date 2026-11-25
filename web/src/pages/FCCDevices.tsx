import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Badge, Button, Card, ErrorBanner, Input, Modal, PageHeader } from '../components/ui'
import type { DispenserItem, FCCDeviceItem, NozzleItem, POSTerminalItem, Station } from '../types'

const emptyForm = {
  device_uid: '', name: '', serial_number: '', hardware_version: '',
  firmware_version: 'v1.0.0', station_id: '', dispenser_id: '', nozzle_id: '',
  pos_terminal_id: '', protocol: 'Wayne_Dart', connection_mode: 'WIFI',
  sim_info: '', calibration_factor: '100', status: 'ACTIVE',
}

export default function FCCDevices() {
  const { can } = useAuth()
  const [devices, setDevices] = useState<FCCDeviceItem[]>([])
  const [stations, setStations] = useState<Station[]>([])
  const [dispensers, setDispensers] = useState<DispenserItem[]>([])
  const [nozzles, setNozzles] = useState<NozzleItem[]>([])
  const [terminals, setTerminals] = useState<POSTerminalItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({ ...emptyForm })

  const load = () => {
    setLoading(true)
    Promise.all([
      api.get<FCCDeviceItem[]>('/fcc-devices'),
      api.get<Station[]>('/stations'),
      api.get<DispenserItem[]>('/dispensers'),
      api.get<NozzleItem[]>('/nozzles'),
      api.get<POSTerminalItem[]>('/payments/terminals'),
    ])
      .then(([f, s, d, n, p]) => {
        setDevices(f); setStations(s); setDispensers(d); setNozzles(n); setTerminals(p)
        if (s.length > 0 && !form.station_id) setForm((prev) => ({ ...prev, station_id: s[0].id }))
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load FCC devices'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const dispensersForStation = dispensers.filter((d) => d.station_id === form.station_id)
  const nozzlesForDispenser = nozzles.filter((n) => n.dispenser_id === form.dispenser_id)
  const terminalsForStation = terminals.filter((t) => t.station_id === form.station_id && t.is_active)

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(''); setSuccess('')
    try {
      await api.post('/quick/fcc', {
        device_uid: form.device_uid.trim(),
        station_id: form.station_id,
      })
      setCreating(false)
      setForm({ ...emptyForm, station_id: form.station_id })
      setSuccess('FCC Controller registered and assigned to a free nozzle. Provision its credential before hardware can send telemetry.')
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to register FCC Controller')
    }
  }

  const toggleOnline = async (id: string) => {
    try { await api.post(`/fcc-devices/${id}/toggle-online`); load() }
    catch (err) { setError(err instanceof Error ? err.message : 'Failed to toggle status') }
  }

  return (
    <>
      <PageHeader
        title="Fuel Control Controllers (FCC)"
        subtitle="Register one controller per nozzle, monitor telemetry and provision device credentials"
        action={<div style={{ display: 'flex', gap: 8 }}>
          {can('fcc_devices', 'create') && <Button onClick={() => setCreating(true)}>+ Register FCC</Button>}
          <Button onClick={load} variant="secondary">↻ Refresh</Button>
        </div>}
      />
      {error && <ErrorBanner message={error} />}
      {success && <div className="notice-success">{success}</div>}

      <div style={{ background: 'rgba(15, 111, 189, 0.08)', border: '1px solid var(--border)', padding: '12px 16px', borderRadius: '8px', marginBottom: '16px', fontSize: '13px' }}>
        <strong>Assignment rule:</strong> station → dispenser → nozzle → POS terminal. A controller cannot be assigned to a dispenser from a different station.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '16px' }}>
        {loading && <div className="empty-state">Loading controllers…</div>}
        {!loading && devices.length === 0 && <div className="empty-state">No FCC Controllers registered yet.</div>}
        {devices.map((f) => (
          <Card key={f.id}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
              <div>
                <strong style={{ fontSize: '16px', fontFamily: 'monospace' }}>{f.device_uid}</strong>
                <div style={{ fontSize: '12px', color: 'var(--muted)' }}>
                  {f.station_name} · {f.dispenser_code} (Nozzle #{f.nozzle_number})
                </div>
              </div>
              <Badge tone={f.is_online ? 'success' : 'danger'}>{f.is_online ? '● ONLINE' : '○ OFFLINE'}</Badge>
            </div>
            <div style={{ background: 'var(--surface-2)', padding: '10px 12px', borderRadius: '8px', fontSize: '12px', display: 'grid', gap: '6px', margin: '10px 0' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Active WAN Link:</span><span><strong style={{ color: 'var(--primary)' }}>{f.connection_mode === 'WIFI' ? 'Wi-Fi' : '4G SIM'}</strong></span></div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Signal:</span><span><strong>{f.signal_strength_dbm} dBm</strong></span></div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Pulser Calibration:</span><span><strong>{f.calibration_factor}</strong> pulses/L</span></div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Firmware:</span><span><code>{f.firmware_version}</code></span></div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Last heartbeat:</span><small>{f.last_heartbeat ? new Date(f.last_heartbeat).toLocaleTimeString() : 'Never'}</small></div>
            </div>
            {can('fcc_devices', 'manage') && (
              <Button variant={f.is_online ? 'secondary' : 'primary'} style={{ width: '100%' }}
                onClick={() => toggleOnline(f.id)}>
                {f.is_online ? 'Simulate Disconnect' : 'Restore Connection'}
              </Button>
            )}
          </Card>
        ))}
      </div>

      {creating && (
        <Modal title="Register FCC Controller" onClose={() => setCreating(false)}>
          <form onSubmit={handleCreate} style={{ display: 'grid', gap: '12px' }}>
            <p className="muted" style={{ fontSize: 13, margin: 0 }}>
              Only the UID in your ESP32 sketch is needed. A free nozzle is assigned automatically.
            </p>
            <Input label="Controller UID" placeholder="e.g. FCC-DEV-A" value={form.device_uid}
              onChange={(e) => setForm({ ...form, device_uid: e.target.value })} required />
            <label className="field"><span>Station</span>
              <select value={form.station_id} required onChange={(e) => setForm({ ...form, station_id: e.target.value })}>
                <option value="">Select station</option>
                {stations.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.code})</option>)}
              </select>
            </label>
            <Button type="submit">Register FCC Controller</Button>
          </form>
        </Modal>
      )}
    </>
  )
}
