import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import { Badge, Button, Card, ErrorBanner, Input, PageHeader } from '../components/ui'

type Exchange = {
  id: string
  direction: 'IN' | 'OUT'
  device_uid: string | null
  endpoint: string
  method: string
  status_code: number | null
  request_json: string | null
  response_json: string | null
  created_at: string | null
}

const ENDPOINTS = [
  { method: 'POST', path: '/api/v1/fcc/prototype/heartbeat', meaning: 'FCC board → backend: online status for the ticker' },
  { method: 'POST', path: '/api/v1/fcc/transaction/initiate', meaning: 'FCC board → backend → OPay: start POS payment' },
  { method: 'GET', path: '/api/v1/fcc/commands/poll', meaning: 'Backend → FCC board: queued PAYMENT_SUCCESS command' },
  { method: 'POST', path: '/api/v1/fcc/commands/ack', meaning: 'FCC board → backend: command received' },
  { method: 'POST', path: '/api/v1/fcc/transaction/complete', meaning: 'FCC board → backend: litres, pulses, discrepancy check' },
  { method: 'PATCH', path: '/api/v1/fcc/calibration', meaning: 'Web MATH or Serial → backend: pulses per litre' },
  { method: 'POST', path: '/api/v1/device/prototype/telemetry', meaning: 'Separate pulser / tank board → backend: raw readings' },
  { method: 'POST', path: '/api/v1/rfid/prototype/register', meaning: 'RFID board → backend: new card UID + home station' },
  { method: 'POST', path: '/api/v1/rfid/authorize', meaning: 'RFID board → backend: wallet pay + queued valve approval' },
  { method: 'POST', path: '/api/v1/opay/webhook', meaning: 'OPay → backend: signed payment result, then command queued' },
]

export default function HardwareJson() {
  const [rows, setRows] = useState<Exchange[]>([])
  const [direction, setDirection] = useState('')
  const [deviceUid, setDeviceUid] = useState('')
  const [loading, setLoading] = useState(true)
  const [auto, setAuto] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    const params = new URLSearchParams({ limit: '100' })
    if (direction) params.set('direction', direction)
    if (deviceUid.trim()) params.set('device_uid', deviceUid.trim())
    api.get<Exchange[]>(`/hardware/exchanges?${params.toString()}`)
      .then(setRows)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load hardware JSON'))
      .finally(() => setLoading(false))
  }, [direction, deviceUid])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!auto) return
    const timer = window.setInterval(load, 5000)
    return () => window.clearInterval(timer)
  }, [auto, load])

  const sample = rows[0]

  return (
    <>
      <PageHeader
        title="Hardware JSON Monitor"
        subtitle="See the exact JSON every ESP32 sends and the exact JSON the software sends back. Nothing is hidden — this is the bench protocol inspector."
        action={
          <div style={{ display: 'flex', gap: '8px' }}>
            <Button variant={auto ? 'primary' : 'secondary'} onClick={() => setAuto(!auto)}>
              {auto ? '● Auto-refresh 5s' : '○ Auto-refresh off'}
            </Button>
            <Button onClick={load} disabled={loading}>{loading ? 'Loading…' : '↻ Refresh'}</Button>
          </div>
        }
      />
      {error && <ErrorBanner message={error} />}

      <Card style={{ marginBottom: '16px' }}>
        <h3 style={{ marginBottom: '8px' }}>How to read this</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '12px', fontSize: '13px' }}>
          <div style={{ background: 'rgba(22,146,91,.10)', padding: '12px', borderRadius: '8px' }}>
            <Badge tone="success">IN</Badge> <strong>Hardware → Software</strong>
            <div style={{ marginTop: '6px', color: 'var(--muted)' }}>The JSON the ESP32 posted, and the backend's reply. Open a row to see both.</div>
          </div>
          <div style={{ background: 'rgba(41,98,196,.10)', padding: '12px', borderRadius: '8px' }}>
            <Badge tone="info">OUT</Badge> <strong>Software → Hardware</strong>
            <div style={{ marginTop: '6px', color: 'var(--muted)' }}>Commands the backend queued for an ESP32 to collect with <code>POLL</code>.</div>
          </div>
        </div>
      </Card>

      <Card style={{ marginBottom: '16px' }}>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <label className="field" style={{ minWidth: '180px' }}>
            <span>Direction</span>
            <select value={direction} onChange={(e) => setDirection(e.target.value)}>
              <option value="">All</option>
              <option value="IN">IN — hardware to software</option>
              <option value="OUT">OUT — software to hardware</option>
            </select>
          </label>
          <div style={{ flex: 1, minWidth: '220px' }}>
            <Input label="Device UID (optional)" placeholder="fcc-matics-001 / PULSE-DEV-01 / card UID" value={deviceUid} onChange={(e) => setDeviceUid(e.target.value)} />
          </div>
          <Button variant="secondary" onClick={() => { setDirection(''); setDeviceUid('') }}>Clear filters</Button>
        </div>
      </Card>

      <Card>
        <h3 style={{ marginBottom: '12px' }}>Latest exchanges ({rows.length})</h3>
        {rows.length === 0 ? (
          <p style={{ color: 'var(--muted)', fontSize: '13px' }}>
            No JSON captured yet. Power an ESP32, open its Serial Monitor, and type <code>HEARTBEAT</code> or <code>SEND</code>.
          </p>
        ) : (
          <div style={{ display: 'grid', gap: '10px' }}>
            {rows.map((row) => (
              <details key={row.id} style={{ border: '1px solid var(--border)', borderRadius: '8px', padding: '10px 12px' }}>
                <summary style={{ cursor: 'pointer', display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap', fontSize: '13px' }}>
                  <Badge tone={row.direction === 'IN' ? 'success' : 'info'}>{row.direction}</Badge>
                  <code>{row.method}</code>
                  <strong>{row.endpoint}</strong>
                  {row.device_uid && <Badge tone="neutral">{row.device_uid}</Badge>}
                  {row.status_code && <span style={{ color: row.status_code >= 400 ? 'var(--danger)' : 'var(--muted)' }}>HTTP {row.status_code}</span>}
                  <span style={{ color: 'var(--muted)', marginLeft: 'auto' }}>{row.created_at ? new Date(row.created_at).toLocaleTimeString() : ''}</span>
                </summary>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '12px', marginTop: '12px' }}>
                  <div>
                    <strong style={{ fontSize: '12px' }}>REQUEST / PAYLOAD SENT</strong>
                    <pre style={{ background: 'var(--surface-2)', padding: '10px', borderRadius: '8px', overflowX: 'auto', fontSize: '11px', whiteSpace: 'pre-wrap' }}>
                      {row.request_json || '(none)'}
                    </pre>
                  </div>
                  <div>
                    <strong style={{ fontSize: '12px' }}>RESPONSE / COMMAND RETURNED</strong>
                    <pre style={{ background: 'var(--surface-2)', padding: '10px', borderRadius: '8px', overflowX: 'auto', fontSize: '11px', whiteSpace: 'pre-wrap' }}>
                      {row.response_json || '(none)'}
                    </pre>
                  </div>
                </div>
              </details>
            ))}
          </div>
        )}
        {sample && (
          <small style={{ display: 'block', marginTop: '12px', color: 'var(--muted)' }}>
            Tip: type <code>JSON ON</code> on a board to print the same JSON in Serial Monitor. Set <code>JSON OFF</code> if the console gets noisy.
          </small>
        )}
      </Card>

      <Card style={{ marginTop: '16px' }}>
        <h3 style={{ marginBottom: '12px' }}>Protocol at a glance</h3>
        <div style={{ overflowX: 'auto' }}>
          <table className="table" style={{ width: '100%', fontSize: '13px' }}>
            <thead><tr><th>Method</th><th>Endpoint</th><th>Direction / meaning</th></tr></thead>
            <tbody>
              {ENDPOINTS.map((e) => (
                <tr key={e.path + e.method}>
                  <td><code>{e.method}</code></td>
                  <td><code>{e.path}</code></td>
                  <td>{e.meaning}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  )
}
