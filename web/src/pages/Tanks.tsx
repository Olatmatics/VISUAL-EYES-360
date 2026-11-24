import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Badge, Button, Card, ErrorBanner, Input, Modal, PageHeader } from '../components/ui'
import type { Station, TankItem } from '../types'

export default function Tanks() {
  const { can } = useAuth()
  const [tanks, setTanks] = useState<TankItem[]>([])
  const [stations, setStations] = useState<Station[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [creating, setCreating] = useState(false)
  const [editingTank, setEditingTank] = useState<TankItem | null>(null)
  const [form, setForm] = useState({
    station_id: '',
    code: '',
    product_code: 'PMS',
    capacity_l: '50000',
    initial_volume_l: '32000',
  })

  const load = () => {
    setLoading(true)
    Promise.all([
      api.get<TankItem[]>('/tanks'),
      api.get<Station[]>('/stations'),
    ])
      .then(([t, s]) => {
        setTanks(t)
        setStations(s)
        if (s.length > 0 && !form.station_id) {
          setForm((prev) => ({ ...prev, station_id: s[0].id }))
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load tanks'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const toggleHatch = async (id: string) => {
    try {
      await api.post(`/tanks/${id}/toggle-hatch`)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to toggle hatch sensor')
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.post('/tanks', form)
      setCreating(false)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create tank')
    }
  }

  return (
    <>
      <PageHeader
        title="Fuel Tank Monitoring & Automated Tank Gauging (ATG)"
        subtitle="Underground storage telemetry, magnetostrictive Modbus RTU probes and ATEX hatch cover security"
        action={
          <div style={{ display: 'flex', gap: '8px' }}>
            {can('tanks', 'create') && <Button onClick={() => setCreating(true)}>+ Register Tank</Button>}
            <Button onClick={load} variant="secondary">↻ Refresh Probes</Button>
          </div>
        }
      />
      {error && <ErrorBanner message={error} />}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '16px' }}>
        {tanks.map((t) => {
          const isFullWarning = t.fill_percentage >= 95
          const isLowWarning = t.fill_percentage <= 15
          return (
            <Card key={t.id} style={{ border: t.hatch_open ? '2px solid var(--danger)' : undefined }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: '18px' }}>{t.code}</h3>
                  <small style={{ color: 'var(--muted)' }}>{t.station_name} · <strong>{t.product_name}</strong></small>
                </div>
                <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                  <Badge tone={t.product_code === 'PMS' ? 'info' : t.product_code === 'AGO' ? 'warning' : 'neutral'}>
                    {t.product_code}
                  </Badge>
                  {t.hatch_open ? (
                    <Badge tone="danger">🚨 HATCH TAMPER</Badge>
                  ) : (
                    <Badge tone="success">🔒 HATCH SECURE</Badge>
                  )}
                </div>
              </div>

              {/* Cylindrical Level Visualization Bar */}
              <div style={{ margin: '14px 0' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', marginBottom: '4px' }}>
                  <span>Physical Volume: <strong>{t.current_volume_l.toLocaleString()} L</strong></span>
                  <span><strong>{t.fill_percentage}%</strong></span>
                </div>
                <div style={{ width: '100%', height: '16px', background: 'var(--surface-2)', borderRadius: '8px', overflow: 'hidden', border: '1px solid var(--border)' }}>
                  <div
                    style={{
                      height: '100%',
                      width: `${Math.min(100, Math.max(0, t.fill_percentage))}%`,
                      background: isLowWarning ? 'var(--danger)' : isFullWarning ? 'var(--warning)' : 'linear-gradient(90deg, var(--accent), var(--primary))',
                      transition: 'width 0.5s ease',
                    }}
                  />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--muted)', marginTop: '4px' }}>
                  <span>Capacity: {t.capacity_l.toLocaleString()} L</span>
                  <span>Ullage: {t.ullage_l.toLocaleString()} L</span>
                </div>
              </div>

              {/* ATG Telemetry Metrics */}
              <div style={{ background: 'var(--surface-2)', padding: '10px 12px', borderRadius: '8px', fontSize: '12px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '12px' }}>
                <div>
                  <span style={{ color: 'var(--muted)' }}>Fuel Level:</span>
                  <div><strong>{t.current_level_mm} mm</strong></div>
                </div>
                <div>
                  <span style={{ color: 'var(--muted)' }}>Water Level:</span>
                  <div>
                    <strong style={{ color: t.current_water_mm > 25 ? 'var(--danger)' : 'var(--text)' }}>
                      {t.current_water_mm} mm {t.current_water_mm > 25 && '⚠'}
                    </strong>
                  </div>
                </div>
                <div>
                  <span style={{ color: 'var(--muted)' }}>Temperature:</span>
                  <div><strong>{t.current_temperature_c} °C</strong></div>
                </div>
                <div>
                  <span style={{ color: 'var(--muted)' }}>Controller UID:</span>
                  <div><code>{t.controller?.device_uid ?? 'None'}</code></div>
                </div>
              </div>

              {can('tanks', 'manage') && (
                <div style={{ display: 'flex', gap: '8px' }}>
                  <Button
                    variant={t.hatch_open ? 'danger' : 'secondary'}
                    style={{ flex: 1, fontSize: '12px' }}
                    onClick={() => toggleHatch(t.id)}
                  >
                    {t.hatch_open ? 'Reset Security Hatch' : 'Trip Hatch Sensor (Test Alert)'}
                  </Button>
                </div>
              )}
            </Card>
          )
        })}
      </div>

      {creating && (
        <Modal title="Register Storage Tank" onClose={() => setCreating(false)}>
          <form onSubmit={handleCreate} style={{ display: 'grid', gap: '12px' }}>
            <label className="field">
              <span>Station</span>
              <select value={form.station_id} onChange={(e) => setForm({ ...form, station_id: e.target.value })} required>
                {stations.map((s) => (
                  <option key={s.id} value={s.id}>{s.name} ({s.code})</option>
                ))}
              </select>
            </label>
            <Input
              label="Tank Code"
              placeholder="e.g. TANK-03-AGO"
              value={form.code}
              onChange={(e) => setForm({ ...form, code: e.target.value })}
              required
            />
            <label className="field">
              <span>Fuel Product</span>
              <select value={form.product_code} onChange={(e) => setForm({ ...form, product_code: e.target.value })}>
                <option value="PMS">Premium Motor Spirit (PMS)</option>
                <option value="AGO">Automotive Gas Oil (AGO / Diesel)</option>
                <option value="DPK">Dual Purpose Kerosene (DPK)</option>
              </select>
            </label>
            <Input
              label="Tank Capacity (Litres)"
              type="number"
              value={form.capacity_l}
              onChange={(e) => setForm({ ...form, capacity_l: e.target.value })}
              required
            />
            <Input
              label="Initial Physical Fuel Volume (Litres)"
              type="number"
              value={form.initial_volume_l}
              onChange={(e) => setForm({ ...form, initial_volume_l: e.target.value })}
              required
            />
            <Button type="submit">Create Storage Tank</Button>
          </form>
        </Modal>
      )}
    </>
  )
}
