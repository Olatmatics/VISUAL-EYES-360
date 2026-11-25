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
      await api.post('/fcc-devices', {
        device_uid: form.device_uid.trim(),
        name: form.name.trim() || undefined,
        serial_number: form.serial_number.trim() || undefined,
        hardware_version: form.hardware_version.trim() || undefined,
        firmware_version: form.firmware_version.trim() || undefined,
        station_id: form.station_id,
        dispenser_id: form.dispenser_id,
        nozzle_id: form.nozzle_id,
        pos_terminal_id: form.pos_terminal_id || undefined,
        protocol: form.protocol.trim() || undefined,
        connection_mode: form.connection_mode,
        sim_info: form.sim_info.trim() || undefined,
        calibration_factor: Number(form.calibration_factor),
        status: form.status,
      })
      setCreating(false)
      setForm({ ...emptyForm, station_id: form.station_id })
      setSuccess('FCC Controller registered. Provision its credential before hardware can send telemetry.')
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
            <div className="form-grid">
              <Input label="Controller device UID" placeholder="e.g. FCC-DEV-A" value={form.device_uid}
                onChange={(e) => setForm({ ...form, device_uid: e.target.value })} required />
              <Input label="Display name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <Input label="Serial number" value={form.serial_number} onChange={(e) => setForm({ ...form, serial_number: e.target.value })} />
              <Input label="Hardware version" value={form.hardware_version} onChange={(e) => setForm({ ...form, hardware_version: e.target.value })} />
              <Input label="Firmware version" value={form.firmware_version} onChange={(e) => setForm({ ...form, firmware_version: e.target.value })} />
              <Input label="Calibration (pulses/L)" type="number" step="0.01" value={form.calibration_factor}
                onChange={(e) => setForm({ ...form, calibration_factor: e.target.value })} required />
            </div>
            <label className="field"><span>Station</span>
              <select value={form.station_id} required onChange={(e) => setForm({ ...form, station_id: e.target.value, dispenser_id: '', nozzle_id: '', pos_terminal_id: '' })}>
                <option value="">Select station</option>
                {stations.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.code})</option>)}
              </select>
            </label>
            <div className="form-grid">
              <label className="field"><span>Dispenser</span>
                <select value={form.dispenser_id} required disabled={!form.station_id}
                  onChange={(e) => setForm({ ...form, dispenser_id: e.target.value, nozzle_id: '', pos_terminal_id: '' })}>
                  <option value="">Select dispenser</option>
                  {dispensersForStation.map((d) => <option key={d.id} value={d.id}>{d.code} · {d.brand || d.manufacturer}</option>)}
                </select>
              </label>
              <label className="field"><span>Nozzle</span>
                <select value={form.nozzle_id} required disabled={!form.dispenser_id}
                  onChange={(e) => setForm({ ...form, nozzle_id: e.target.value })}>
                  <option value="">Select nozzle</option>
                  {nozzlesForDispenser.map((n) => <option key={n.id} value={n.id}>Nozzle {n.number} · ₦{n.price}/L</option>)}
                </select>
              </label>
              <label className="field"><span>OPay POS terminal</span>
                <select value={form.pos_terminal_id} disabled={!form.station_id}
                  onChange={(e) => setForm({ ...form, pos_terminal_id: e.target.value })}>
                  <option value="">None (assign later)</option>
                  {terminalsForStation.map((t) => <option key={t.id} value={t.id}>{t.terminal_id} · {t.dispenser_code || 'unassigned'}</option>)}
                </select>
              </label>
              <label className="field"><span>Connection mode</span>
                <select value={form.connection_mode} onChange={(e) => setForm({ ...form, connection_mode: e.target.value })}>
                  <option value="WIFI">Wi-Fi (primary)</option>
                  <option value="SIM">SIM cellular</option>
                </select>
              </label>
              <Input label="Protocol" value={form.protocol} onChange={(e) => setForm({ ...form, protocol: e.target.value })} />
              <Input label="SIM / network info" value={form.sim_info} onChange={(e) => setForm({ ...form, sim_info: e.target.value })} />
            </div>
            <Button type="submit">Register FCC Controller</Button>
          </form>
        </Modal>
      )}
    </>
  )
}
