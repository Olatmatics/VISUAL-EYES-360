import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Badge, Button, Card, EmptyState, ErrorBanner, Input, PageHeader } from '../components/ui'
import type { GeoLga, GeoState } from '../types'

type GeneratedNozzle = {
  id: string
  code: string
  number: number
  price: number
  station_code: string
  dispenser_code: string
  fcc_uid: string
  pos_terminal_id: string
}

type Generated = {
  station: { id: string; code: string; name: string }
  dispenser: { id: string; code: string; name: string }
  nozzles: GeneratedNozzle[]
  sketches: { board01: string; board03: string; board05: string }
  message: string
}

type SavedNozzle = {
  id: string
  code: string | null
  number: number
  price: number
  fcc_uid: string | null
  pos_terminal_id: string | null
}
type SavedPump = { id: string; code: string; name: string; nozzles: SavedNozzle[] }
type SavedStation = { id: string; code: string; name: string; dispensers: SavedPump[] }
type Records = { stations: SavedStation[] }

type IdField = { label: string; value: string }

const asText = (value: unknown) => (value === undefined || value === null ? '' : String(value))

function CopyChip({ label, value, copied, onCopy, tone = 'neutral' }: {
  label: string
  value: string
  copied: string
  onCopy: (field: IdField) => void
  tone?: 'neutral' | 'success' | 'info'
}) {
  const key = `${label}:${value}`
  return (
    <button
      type="button"
      className={`id-chip ${copied === key ? 'copied' : ''}`}
      onClick={() => onCopy({ label, value })}
      disabled={!value}
      title={`Copy ${label}`}
    >
      <span className="id-chip-label">{label}</span>
      <code>{value || '—'}</code>
      <span className="id-chip-action">{copied === key ? '✓ Copied' : '⧉'}</span>
      {tone !== 'neutral' && <Badge tone={tone}>short ID</Badge>}
    </button>
  )
}

function CopyBlock({ title, value, copied, onCopy }: {
  title: string
  value: string
  copied: string
  onCopy: (field: IdField) => void
}) {
  const key = `${title}:${value}`
  return (
    <Card style={{ marginTop: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <strong>{title}</strong>
        <Button variant="secondary" onClick={() => onCopy({ label: title, value })}>
          {copied === key ? '✓ Copied' : '⧉ Copy code'}
        </Button>
      </div>
      <pre className="generated-code">{value}</pre>
    </Card>
  )
}

export default function HardwareIds() {
  const { user } = useAuth()
  const [states, setStates] = useState<GeoState[]>([])
  const [lgas, setLgas] = useState<GeoLga[]>([])
  const [form, setForm] = useState({
    station_name: '',
    station_code: '',
    state_id: '',
    lga_id: '',
    city: '',
    address: '',
    manager_name: '',
    manager_phone: '',
    dispenser_name: '',
    nozzle_count: '2',
    price: '1000',
    pulses_per_litre: '100',
    wifi_ssid: 'cypher',
    wifi_pass: '12345678',
    backend_url: 'http://172.25.0.37:8000',
    api_key: '',
  })
  const [result, setResult] = useState<Generated | null>(null)
  const [records, setRecords] = useState<Records>({ stations: [] })
  const [tab, setTab] = useState<'generate' | 'saved'>('generate')
  const [copied, setCopied] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const loadRecords = () => {
    api.get<Records>('/hardware-ids/records').then(setRecords).catch((err) => {
      setError(err instanceof Error ? err.message : 'Could not load saved IDs')
    })
  }

  useEffect(() => {
    api.get<GeoState[]>('/geo/states').then(setStates).catch(() => setStates([]))
    loadRecords()
  }, [])
  useEffect(() => {
    if (!form.state_id) { setLgas([]); return }
    api.get<GeoLga[]>(`/geo/states/${form.state_id}/lgas`).then(setLgas).catch(() => setLgas([]))
  }, [form.state_id])

  const fields = useMemo(() => {
    if (!result) return [] as IdField[]
    const list: IdField[] = [
      { label: 'Station code', value: result.station.code },
      { label: 'Dispenser code', value: result.dispenser.code },
    ]
    result.nozzles.forEach((nozzle) => {
      list.push(
        { label: `Nozzle ${nozzle.number}`, value: nozzle.code },
        { label: `FCC UID ${nozzle.number}`, value: nozzle.fcc_uid },
        { label: `POS ID ${nozzle.number}`, value: nozzle.pos_terminal_id },
      )
    })
    return list
  }, [result])

  const copy = async (field: IdField) => {
    let ok = false
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(field.value)
        ok = true
      }
    } catch {
      // Non-secure LAN addresses need the fallback below.
    }
    if (!ok) {
      const area = document.createElement('textarea')
      area.value = field.value
      area.style.position = 'fixed'
      area.style.opacity = '0'
      document.body.appendChild(area)
      area.select()
      ok = document.execCommand('copy')
      area.remove()
    }
    setCopied(`${field.label}:${field.value}`)
    window.setTimeout(() => setCopied(''), 1800)
    if (!ok) setError('Copy was blocked by the browser — select the text and copy manually.')
  }

  const generate = async (event: React.FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    setResult(null)
    try {
      const created = await api.post<Generated>('/hardware-ids/generate', {
        ...form,
        nozzle_count: Number(form.nozzle_count),
        price: Number(form.price),
        pulses_per_litre: Number(form.pulses_per_litre),
      })
      setResult(created)
      loadRecords()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not generate IDs')
    } finally {
      setBusy(false)
    }
  }

  if (!user?.is_super_admin) {
    return (
      <Card className="center-card">
        <h2>Administrator only</h2>
        <p>Only the Superior Administrator can generate hardware IDs.</p>
      </Card>
    )
  }

  return (
    <>
      <PageHeader
        title="Generate Hardware IDs"
        subtitle="Type a station name. The system creates short, unique IDs and ready-to-upload ESP32 code — no UUID copying."
        action={<Badge tone="warning">Administrator only</Badge>}
      />

      <Card style={{ marginBottom: 16 }}>
        <div className="tabs" style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          <Button variant={tab === 'generate' ? 'primary' : 'secondary'} onClick={() => setTab('generate')}>Generate new IDs</Button>
          <Button variant={tab === 'saved' ? 'primary' : 'secondary'} onClick={() => { setTab('saved'); loadRecords() }}>Saved IDs</Button>
        </div>
        <div className="notice compact">
          Short codes are accepted anywhere a UUID was required. Copy a chip into Serial Monitor, or paste a whole code block into the sketch and upload.
        </div>
        {error && <ErrorBanner message={error} />}
      </Card>

      {tab === 'generate' && (
        <>
          <Card>
            <form id="hardware-ids-form" className="form-grid" onSubmit={generate}>
              <Input label="1. Station name" placeholder="e.g. Matics Oil and Gas" value={form.station_name} required
                onChange={(e) => setForm({ ...form, station_name: e.target.value })} />
              <Input label="Station code (optional)" placeholder="Leave blank to generate, e.g. ST-7K3M2Q"
                value={form.station_code} onChange={(e) => setForm({ ...form, station_code: e.target.value })} />
              <label className="field"><span>State / FCT</span>
                <select value={form.state_id} onChange={(e) => setForm({ ...form, state_id: e.target.value, lga_id: '' })}>
                  <option value="">Select state (optional)</option>
                  {states.map((state) => <option key={state.id} value={state.id}>{state.name}</option>)}
                </select>
              </label>
              <label className="field"><span>LGA</span>
                <select value={form.lga_id} disabled={!form.state_id} onChange={(e) => setForm({ ...form, lga_id: e.target.value })}>
                  <option value="">Select LGA (optional)</option>
                  {lgas.map((lga) => <option key={lga.id} value={lga.id}>{lga.name}</option>)}
                </select>
              </label>
              <Input label="City / Town" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} />
              <Input label="Address" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
              <Input label="Manager name" value={form.manager_name} onChange={(e) => setForm({ ...form, manager_name: e.target.value })} />
              <Input label="Manager phone" value={form.manager_phone} onChange={(e) => setForm({ ...form, manager_phone: e.target.value })} />
              <Input label="Pump name (optional)" placeholder="e.g. Pump 1" value={form.dispenser_name}
                onChange={(e) => setForm({ ...form, dispenser_name: e.target.value })} />
              <Input label="Number of nozzles" type="number" min={1} max={12} value={form.nozzle_count}
                onChange={(e) => setForm({ ...form, nozzle_count: e.target.value })} />
              <Input label="Price per litre (₦)" type="number" min={1} step="0.01" value={form.price}
                onChange={(e) => setForm({ ...form, price: e.target.value })} />
              <Input label="Pulses per litre" type="number" min={1} step="0.01" value={form.pulses_per_litre}
                onChange={(e) => setForm({ ...form, pulses_per_litre: e.target.value })} />
              <Input label="Wi-Fi name (SSID)" value={form.wifi_ssid} onChange={(e) => setForm({ ...form, wifi_ssid: e.target.value })} />
              <Input label="Wi-Fi password" value={form.wifi_pass} onChange={(e) => setForm({ ...form, wifi_pass: e.target.value })} />
              <Input label="Backend URL" value={form.backend_url} onChange={(e) => setForm({ ...form, backend_url: e.target.value })} />
              <Input label="Ingest API key (Board 05, optional)" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} />
            </form>
            <div style={{ marginTop: 16 }}>
              <Button type="submit" form="hardware-ids-form" disabled={busy} style={{ fontSize: 15, padding: '11px 18px' }}>
                {busy ? 'Generating…' : '✓ Generate IDs and ESP32 code'}
              </Button>
            </div>
          </Card>

          {result && (
            <>
              <Card style={{ marginTop: 16 }}>
                <h2>Copy the IDs you need</h2>
                <div className="notice compact">{result.message}</div>
                <div className="id-chips">
                  {fields.map((field) => (
                    <CopyChip key={`${field.label}-${field.value}`} label={field.label} value={field.value}
                      copied={copied} onCopy={copy} tone={field.label.startsWith('Station') || field.label.startsWith('Dispenser') || field.label.startsWith('Nozzle') ? 'success' : 'info'} />
                  ))}
                </div>
                <p className="muted" style={{ fontSize: 12, marginTop: 12 }}>
                  Internal database UUIDs still exist, but nothing here requires you to type them.
                </p>
              </Card>

              <CopyBlock title="Board 01 — FCC pump controller" value={result.sketches.board01} copied={copied} onCopy={copy} />
              <CopyBlock title="Board 03 — independent pulser reader" value={result.sketches.board03} copied={copied} onCopy={copy} />
              <CopyBlock title="Board 05 — RFID registrar / wallet" value={result.sketches.board05} copied={copied} onCopy={copy} />
            </>
          )}
        </>
      )}

      {tab === 'saved' && (
        <Card>
          <h2>Saved short IDs</h2>
          {records.stations.length === 0 ? (
            <EmptyState title="No IDs generated yet" message="Generate a set above, then every code stays here for copying." />
          ) : records.stations.map((station) => (
            <div key={station.id} className="saved-station">
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <strong>{station.name}</strong>
                <CopyChip label="Station" value={station.code} copied={copied} onCopy={copy} tone="success" />
              </div>
              {station.dispensers.map((pump) => (
                <div key={pump.id} className="saved-pump">
                  <CopyChip label="Pump" value={pump.code} copied={copied} onCopy={copy} tone="success" />
                  {pump.nozzles.map((nozzle) => (
                    <div className="id-chips" key={nozzle.id}>
                      <CopyChip label={`Nozzle ${nozzle.number}`} value={asText(nozzle.code)} copied={copied} onCopy={copy} tone="success" />
                      <CopyChip label={`FCC ${nozzle.number}`} value={asText(nozzle.fcc_uid)} copied={copied} onCopy={copy} />
                      <CopyChip label={`POS ${nozzle.number}`} value={asText(nozzle.pos_terminal_id)} copied={copied} onCopy={copy} />
                    </div>
                  ))}
                </div>
              ))}
            </div>
          ))}
        </Card>
      )}
    </>
  )
}
