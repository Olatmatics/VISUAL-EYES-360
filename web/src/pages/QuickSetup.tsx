import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { Badge, Button, Card, ErrorBanner, Input, PageHeader } from '../components/ui'

type Result = {
  ok: boolean
  message: string
  summary: string
  station: { id: string; name: string; code: string; created: boolean }
  pumps: { id: string; code: string; nozzles: string[] }[]
  tanks: { id: string; code: string }[]
  controllers: { uid: string; status: string; nozzle_id?: string }[]
  cards: { uid: string; status: string }[]
}

type Status = { stations: number; pumps: number; nozzles: number; tanks: number; controllers: number; cards: number }

export default function QuickSetup() {
  const [status, setStatus] = useState<Status | null>(null)
  const [result, setResult] = useState<Result | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({
    station_name: '', pump_count: '1', nozzles_per_pump: '2',
    price_per_litre: '1000', tank_capacity_l: '30000',
    controller_uids: '', card_uid: '',
  })

  const load = () => api.get<Status>('/simple/status').then(setStatus).catch(() => setStatus(null))
  useEffect(() => { load() }, [])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(''); setResult(null); setBusy(true)
    try {
      const r = await api.post<Result>('/simple/setup', form)
      setResult(r)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Setup failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader
        title="Set Up Your Station"
        subtitle="Type a name and a few numbers. Everything else is created for you automatically."
      />

      <Card style={{ marginBottom: 16 }}>
        <h3>What is already registered</h3>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
          {status ? (
            <>
              <Badge tone="success">{status.stations} stations</Badge>
              <Badge tone="info">{status.pumps} pumps</Badge>
              <Badge tone="info">{status.nozzles} nozzles</Badge>
              <Badge tone="info">{status.tanks} tanks</Badge>
              <Badge tone="info">{status.controllers} controllers</Badge>
              <Badge tone="info">{status.cards} cards</Badge>
            </>
          ) : <span className="muted">Loading…</span>}
        </div>
      </Card>

      {error && <ErrorBanner message={error} />}

      <Card>
        <div style={{ background: 'rgba(22,146,91,.10)', border: '1px solid var(--success)',
                      padding: '10px 14px', borderRadius: 8, marginBottom: 16, fontSize: 13 }}>
          <strong>You do not need to register anything else.</strong> Station codes, pump codes,
          nozzle records, tanks and device assignments are all generated automatically.
        </div>

        <form onSubmit={submit} style={{ display: 'grid', gap: 16 }}>
          <Input label="1. Station name" placeholder="e.g. Abuja Main Station"
            value={form.station_name}
            onChange={(e) => setForm({ ...form, station_name: e.target.value })} required />

          <div className="form-grid">
            <Input label="2. How many pumps?" type="number" min={1} max={10}
              value={form.pump_count}
              onChange={(e) => setForm({ ...form, pump_count: e.target.value })} />
            <label className="field"><span>3. Nozzles per pump</span>
              <select value={form.nozzles_per_pump}
                onChange={(e) => setForm({ ...form, nozzles_per_pump: e.target.value })}>
                <option value="2">Two nozzles (double)</option>
                <option value="1">One nozzle (single)</option>
              </select>
            </label>
            <Input label="4. Price per litre (₦)" type="number" step="0.01"
              value={form.price_per_litre}
              onChange={(e) => setForm({ ...form, price_per_litre: e.target.value })} />
            <Input label="5. Tank size (litres)" type="number"
              value={form.tank_capacity_l}
              onChange={(e) => setForm({ ...form, tank_capacity_l: e.target.value })} />
          </div>

          <label className="field"><span>6. Controller UIDs — one per line (optional)</span>
            <textarea rows={3} placeholder={'FCC-DEV-A\nFCC-DEV-B'}
              value={form.controller_uids}
              onChange={(e) => setForm({ ...form, controller_uids: e.target.value })} />
            <small className="muted">Copy these exact names into your ESP32 sketches.</small>
          </label>

          <Input label="7. RFID card UID (optional)"
            value={form.card_uid}
            onChange={(e) => setForm({ ...form, card_uid: e.target.value })}
            placeholder="Place the card on the reader and type the UID from Serial Monitor" />

          <Button type="submit" disabled={busy} style={{ fontSize: 16, padding: '12px 20px' }}>
            {busy ? 'Setting up…' : '✓ Set Up Everything'}
          </Button>
        </form>
      </Card>

      {result?.ok && (
        <Card style={{ marginTop: 16 }}>
          <h3 style={{ color: 'var(--success)' }}>✓ {result.message}</h3>
          <p style={{ fontSize: 15, fontWeight: 600 }}>{result.summary}</p>
          <div style={{ display: 'grid', gap: 8, fontSize: 13 }}>
            <div><strong>Station:</strong> {result.station.name} — code <code>{result.station.code}</code></div>
            {result.pumps.map((p, i) => (
              <div key={p.id}><strong>Pump {i + 1}:</strong> <code>{p.code}</code> — {p.nozzles.length} nozzle(s)</div>
            ))}
            {result.tanks.map((t, i) => (
              <div key={t.id}><strong>Tank {i + 1}:</strong> <code>{t.code}</code></div>
            ))}
            {result.controllers.map((c) => (
              <div key={c.uid}><strong>Controller:</strong> <code>{c.uid}</code> — {c.status}</div>
            ))}
            {result.cards.map((c) => (
              <div key={c.uid}><strong>Card:</strong> <code>{c.uid}</code> — {c.status}</div>
            ))}
          </div>
          <p className="muted" style={{ marginTop: 14, marginBottom: 0, fontSize: 13 }}>
            Next: flash each ESP32 with the matching UID, put that UID in the sketch, then provision the
            device credential and start the Serial Monitor.
          </p>
        </Card>
      )}
    </>
  )
}
