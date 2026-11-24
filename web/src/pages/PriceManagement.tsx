import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Badge, Button, Card, ErrorBanner, Input, PageHeader } from '../components/ui'
import type { PriceHistoryItem, PriceItem, Station } from '../types'

export default function PriceManagement() {
  const { user, can } = useAuth()
  const [prices, setPrices] = useState<PriceItem[]>([])
  const [history, setHistory] = useState<PriceHistoryItem[]>([])
  const [stations, setStations] = useState<Station[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [scope, setScope] = useState<'NOZZLE' | 'STATION' | 'NATIONWIDE'>('STATION')
  const [targetStationId, setTargetStationId] = useState('')
  const [targetNozzleId, setTargetNozzleId] = useState('')
  const [productCode, setProductCode] = useState('PMS')
  const [newPrice, setNewPrice] = useState('850')
  const [updating, setUpdating] = useState(false)

  const load = () => {
    setLoading(true)
    Promise.all([
      api.get<PriceItem[]>('/prices'),
      api.get<PriceHistoryItem[]>('/prices/history'),
      api.get<Station[]>('/stations'),
    ])
      .then(([p, h, s]) => {
        setPrices(p)
        setHistory(h)
        setStations(s)
        if (s.length > 0 && !targetStationId) setTargetStationId(s[0].id)
        if (p.length > 0 && !targetNozzleId) setTargetNozzleId(p[0].nozzle_id)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load prices'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    setUpdating(true)
    try {
      const res = await api.post<any>('/prices/update', {
        scope,
        new_price: parseFloat(newPrice),
        product_code: productCode,
        station_id: targetStationId,
        nozzle_id: targetNozzleId,
      })
      setSuccess(`Price updated successfully across ${res.nozzles_updated} nozzles.`)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Price update failed')
    } finally {
      setUpdating(false)
    }
  }

  return (
    <>
      <PageHeader
        title="Centralized Fuel Price Management"
        subtitle="Remote electronic price dispatching across individual nozzles, stations or nationwide"
        action={<Button onClick={load} variant="secondary">↻ Refresh Prices</Button>}
      />
      {error && <ErrorBanner message={error} />}
      {success && (
        <div style={{ background: 'rgba(22, 146, 91, 0.12)', border: '1px solid var(--success)', padding: '12px 16px', borderRadius: '8px', color: 'var(--success)', marginBottom: '16px', fontSize: '13px', fontWeight: 600 }}>
          ✓ {success}
        </div>
      )}

      {/* Price Dispatch Form */}
      {can('prices', 'create') && (
        <Card style={{ marginBottom: '20px' }}>
          <h3 style={{ marginBottom: '12px' }}>Remote Price Dispatch Terminal</h3>
          <form onSubmit={handleUpdate} style={{ display: 'grid', gap: '14px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
              <label className="field">
                <span>Update Scope</span>
                <select value={scope} onChange={(e) => setScope(e.target.value as any)}>
                  <option value="STATION">Single Station</option>
                  <option value="NOZZLE">Individual Nozzle</option>
                  {user?.is_super_admin && <option value="NATIONWIDE">🌍 Nationwide (All Stations)</option>}
                </select>
              </label>

              {scope === 'STATION' && (
                <label className="field">
                  <span>Target Station</span>
                  <select value={targetStationId} onChange={(e) => setTargetStationId(e.target.value)}>
                    {stations.map((s) => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                  </select>
                </label>
              )}

              {scope === 'NOZZLE' && (
                <label className="field">
                  <span>Target Nozzle</span>
                  <select value={targetNozzleId} onChange={(e) => setTargetNozzleId(e.target.value)}>
                    {prices.map((p) => (
                      <option key={p.nozzle_id} value={p.nozzle_id}>
                        {p.station_name} — {p.dispenser_code} (Nozzle #{p.nozzle_number} {p.product_code})
                      </option>
                    ))}
                  </select>
                </label>
              )}

              <label className="field">
                <span>Fuel Product</span>
                <select value={productCode} onChange={(e) => setProductCode(e.target.value)}>
                  <option value="PMS">Premium Motor Spirit (PMS)</option>
                  <option value="AGO">Automotive Gas Oil (AGO / Diesel)</option>
                  <option value="DPK">Dual Purpose Kerosene (DPK)</option>
                </select>
              </label>

              <Input
                label="New Unit Price (NGN / Litre)"
                type="number"
                value={newPrice}
                onChange={(e) => setNewPrice(e.target.value)}
                required
              />
            </div>

            <Button type="submit" disabled={updating}>
              {updating ? 'Transmitting to Dispenser CPUs…' : `Transmit New Price: ₦${newPrice}/L`}
            </Button>
          </form>
        </Card>
      )}

      {/* Current Prices Table */}
      <Card style={{ marginBottom: '20px' }}>
        <h3 style={{ marginBottom: '12px' }}>Current Active Forecourt Unit Prices</h3>
        <div style={{ overflowX: 'auto' }}>
          <table className="table" style={{ width: '100%', fontSize: '13px' }}>
            <thead>
              <tr>
                <th>Station</th>
                <th>Dispenser</th>
                <th>Nozzle</th>
                <th>Product</th>
                <th>Active Unit Price</th>
                <th>Protocol Status</th>
              </tr>
            </thead>
            <tbody>
              {prices.map((p) => (
                <tr key={p.nozzle_id}>
                  <td><strong>{p.station_name}</strong></td>
                  <td>{p.dispenser_code}</td>
                  <td>Nozzle #{p.nozzle_number}</td>
                  <td><strong>{p.product_code}</strong></td>
                  <td><strong style={{ color: 'var(--primary)', fontSize: '15px' }}>₦{p.price.toFixed(2)}/L</strong></td>
                  <td><Badge tone={p.status === 'CONFIRMED' ? 'success' : 'warning'}>{p.status || 'PENDING'}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Price History Audit Trail */}
      <Card>
        <h3 style={{ marginBottom: '12px' }}>Price Modification Audit Trail</h3>
        <div style={{ overflowX: 'auto' }}>
          <table className="table" style={{ width: '100%', fontSize: '12px' }}>
            <thead>
              <tr>
                <th>Date / Time</th>
                <th>Product</th>
                <th>Previous Price</th>
                <th>New Confirmed Price</th>
                <th>Authorized User</th>
                <th>Dispenser Status</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h) => (
                <tr key={h.id}>
                  <td>{new Date(h.created_at).toLocaleString()}</td>
                  <td><strong>{h.product_code}</strong></td>
                  <td>₦{h.previous_price.toFixed(2)}</td>
                  <td><strong style={{ color: 'var(--success)' }}>₦{h.new_price.toFixed(2)}</strong></td>
                  <td><code>{h.changed_by}</code></td>
                  <td><Badge tone={h.status === 'CONFIRMED' ? 'success' : 'warning'}>{h.status || 'PENDING'}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  )
}
