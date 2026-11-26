import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Badge, Button, Card, ErrorBanner, Input, PageHeader } from '../components/ui'
import type { FCCDeviceItem } from '../types'

type Calibration = {
  device_uid: string
  pulses_per_litre: number
  station_id: string | null
  nozzle_id: string | null
  dispenser_id: string | null
}

export default function PulseMath() {
  const { can } = useAuth()
  const [devices, setDevices] = useState<FCCDeviceItem[]>([])
  const [selected, setSelected] = useState('')
  const [ppl, setPpl] = useState('100')
  const [pps, setPps] = useState('0')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const load = () => {
    setLoading(true)
    api.get<FCCDeviceItem[]>('/fcc-devices')
      .then((rows) => {
        setDevices(rows)
        const uid = selected || rows[0]?.device_uid || ''
        setSelected(uid)
        if (uid) {
          const device = rows.find((d) => d.device_uid === uid)
          setPpl(String(device?.calibration_factor ?? 100))
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load FCC devices'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const device = useMemo(
    () => devices.find((d) => d.device_uid === selected),
    [devices, selected],
  )

  const readFromBackend = async () => {
    if (!selected) return
    setBusy(true)
    setError('')
    try {
      const cal = await api.get<Calibration>(`/fcc/calibration?device_uid=${encodeURIComponent(selected)}`)
      setPpl(String(cal.pulses_per_litre))
      setNotice(`Loaded ${cal.pulses_per_litre} pulses/L for ${cal.device_uid}.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not read calibration')
    } finally {
      setBusy(false)
    }
  }

  const save = async () => {
    if (!selected) { setError('Select an FCC controller first'); return }
    const value = Number(ppl)
    if (!Number.isFinite(value) || value <= 0) { setError('Pulses per litre must be greater than zero'); return }
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const res = await api.patch<{ device_uid: string; pulses_per_litre: number; formula: string }>(
        '/fcc/calibration',
        { device_uid: selected, pulses_per_litre: value },
      )
      setPpl(String(res.pulses_per_litre))
      setNotice(`Saved. ${res.formula}`)
      setDevices((prev) => prev.map((d) => d.device_uid === selected ? { ...d, calibration_factor: res.pulses_per_litre } : d))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save calibration')
    } finally {
      setBusy(false)
    }
  }

  const pplNum = Number(ppl) || 1
  const ppsNum = Number(pps) || 0
  const litresPerPulse = 1 / pplNum
  const litresPerSecond = ppsNum / pplNum
  const secondsForFiveLitres = ppsNum > 0 ? (5 * pplNum) / ppsNum : 0

  return (
    <>
      <PageHeader
        title="Pulse MATH — Pulses → Litres"
        subtitle="Set the exact pulse-per-unit value from the web or from Serial Monitor. The separate pulser ESP32 and the FCC board both read this value."
        action={<Button variant="secondary" onClick={load} disabled={loading}>↻ Refresh</Button>}
      />
      {error && <ErrorBanner message={error} />}
      {notice && (
        <div style={{ background: 'rgba(22,146,91,.12)', border: '1px solid var(--success)', padding: '12px 16px', borderRadius: '8px', marginBottom: '16px', fontSize: '13px' }}>
          ✓ {notice}
        </div>
      )}

      <Card style={{ marginBottom: '16px' }}>
        <h3 style={{ marginBottom: '12px' }}>1 · Choose the controller / pump</h3>
        <label className="field">
          <span>FCC Controller</span>
          <select value={selected} onChange={(e) => {
            const uid = e.target.value
            setSelected(uid)
            const d = devices.find((x) => x.device_uid === uid)
            setPpl(String(d?.calibration_factor ?? 100))
            setNotice('')
          }}>
            {devices.map((d) => (
              <option key={d.id} value={d.device_uid}>
                {d.device_uid} · {d.station_name} · Nozzle {d.nozzle_number}
              </option>
            ))}
          </select>
        </label>
        {device && (
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '10px' }}>
            <Badge tone={device.is_online ? 'success' : 'neutral'}>{device.is_online ? 'Online' : 'Offline'}</Badge>
            <Badge tone="info">Dispenser {device.dispenser_code || '—'}</Badge>
            <Badge tone="neutral">POS {device.pos_terminal_code || 'unassigned'}</Badge>
          </div>
        )}
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
        <Card>
          <h3 style={{ marginBottom: '12px' }}>2 · Pulse calibration (MATH)</h3>
          <div style={{ display: 'grid', gap: '12px' }}>
            <Input
              label="Pulses per litre / unit"
              type="number"
              min="0.01"
              step="0.01"
              value={ppl}
              onChange={(e) => setPpl(e.target.value)}
            />
            <Input
              label="Expected pulses per second (optional)"
              type="number"
              min="0"
              step="0.01"
              value={pps}
              onChange={(e) => setPps(e.target.value)}
            />
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <Button onClick={save} disabled={busy || loading || !can('fcc_devices', 'edit')}>
                {busy ? 'Saving…' : 'Save to backend'}
              </Button>
              <Button variant="secondary" onClick={readFromBackend} disabled={busy || loading}>Read from backend</Button>
            </div>
            <small style={{ color: 'var(--muted)' }}>
              How to measure: run a known 10 L test, count pulses, then set pulses/L = pulses ÷ 10.
              Example: 1000 pulses for 10 L → 100 pulses/L. Nozzle price is separate and set on the nozzle/dispenser page.
            </small>
          </div>
        </Card>

        <Card>
          <h3 style={{ marginBottom: '12px' }}>3 · Live conversion</h3>
          <div className="admin-stat-grid" style={{ display: 'grid', gap: '8px' }}>
            <div><strong>Formula</strong><div><code>litres = raw_pulse_count ÷ {pplNum}</code></div></div>
            <div><strong>1 pulse</strong><div><code>{litresPerPulse.toFixed(5)} L</code></div></div>
            <div><strong>1000 pulses</strong><div><code>{(1000 / pplNum).toFixed(3)} L</code></div></div>
            <div><strong>Pulse rate</strong><div><code>{ppsNum} pps → {litresPerSecond.toFixed(4)} L/s ({litresPerSecond * 60 >= 0 ? (litresPerSecond * 60).toFixed(2) : '0.00'} L/min)</code></div></div>
            <div><strong>Time for 5 L</strong><div><code>{secondsForFiveLitres > 0 ? secondsForFiveLitres.toFixed(1) + ' s' : 'set a pulse rate'}</code></div></div>
          </div>
        </Card>
      </div>

      <Card style={{ marginTop: '16px' }}>
        <h3 style={{ marginBottom: '8px' }}>Same setting from Serial Monitor (bench)</h3>
        <p style={{ fontSize: '13px', lineHeight: 1.6 }}>
          You do not have to use this page. Type these commands in the Serial Monitor of each board:
        </p>
        <pre style={{ background: 'var(--surface-2)', padding: '12px', borderRadius: '8px', overflowX: 'auto', fontSize: '12px' }}>
{`# FCC board (board 1)
CONFIG
CAL SET ${pplNum}
CAL FETCH

# Separate pulser board (board 3)
SET FCC ${selected || 'YOUR_FCC_UID'}
SET PPL ${pplNum}
SET PPS ${ppsNum || 0}
MATH 1000
MATH RATE ${ppsNum || 10}
SEND`}
        </pre>
        <small style={{ color: 'var(--muted)' }}>
          The web page and Serial commands write the same backend field. Whichever you use last wins.
        </small>
      </Card>
    </>
  )
}
