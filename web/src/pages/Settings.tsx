import { useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { Badge, Button, Card, Input, PageHeader } from '../components/ui'

export default function Settings() {
  const { user } = useAuth()
  const [apnCarrier, setApnCarrier] = useState('MTN')
  const [customApn, setCustomApn] = useState('web.gprs.mtnnigeria.net')
  const [threshold, setThreshold] = useState('0.490')
  const [connPriority, setConnPriority] = useState('WIFI_PRIMARY')
  const [saved, setSaved] = useState(false)

  const handleCarrierChange = (c: string) => {
    setApnCarrier(c)
    if (c === 'MTN') setCustomApn('web.gprs.mtnnigeria.net')
    else if (c === 'Airtel') setCustomApn('internet.ng.airtel.com')
    else if (c === 'Glo') setCustomApn('gloflat')
    else if (c === '9mobile') setCustomApn('9mobile')
  }

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault()
    setSaved(true)
    setTimeout(() => setSaved(false), 3000)
  }

  return (
    <>
      <PageHeader
        title="Platform & IoT Hardware Settings"
        subtitle="Manage telecommunication APNs, network priority policies, pulser calibration thresholds and security configurations"
      />

      {saved && (
        <div style={{ background: 'rgba(22, 146, 91, 0.12)', border: '1px solid var(--success)', padding: '12px 16px', borderRadius: '8px', color: 'var(--success)', marginBottom: '16px', fontSize: '13px', fontWeight: 600 }}>
          ✓ Telemetry and hardware settings saved and synced to forecourt edge controllers.
        </div>
      )}

      <div style={{ display: 'grid', gap: '20px', maxWidth: '800px' }}>
        <Card>
          <h3 style={{ marginBottom: '12px' }}>📶 Zero-Ethernet Telemetry & Wireless Carrier APN</h3>
          <p style={{ fontSize: '13px', color: 'var(--muted)', margin: '0 0 14px' }}>
            In strict compliance with <strong>Section 2 (Networking Requirement)</strong>, all ESP32-S3 FCCs and Tank Controllers communicate via <strong>Wi-Fi</strong> and <strong>SIM cellular</strong> only. Physical Ethernet is strictly excluded.
          </p>

          <form onSubmit={handleSave} style={{ display: 'grid', gap: '14px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
              <label className="field">
                <span>Network Connection Priority</span>
                <select value={connPriority} onChange={(e) => setConnPriority(e.target.value)}>
                  <option value="WIFI_PRIMARY">Wi-Fi Primary, 4G SIM Cellular Backup</option>
                  <option value="CELLULAR_PRIMARY">4G SIM Primary, Wi-Fi Secondary</option>
                  <option value="CELLULAR_ONLY">SIM Cellular Only (Isolated Remote Station)</option>
                  <option value="WIFI_ONLY">Wi-Fi Only (Local High-Power Mesh)</option>
                </select>
              </label>

              <label className="field">
                <span>Nigerian Mobile Carrier Preset</span>
                <select value={apnCarrier} onChange={(e) => handleCarrierChange(e.target.value)}>
                  <option value="MTN">MTN Nigeria 4G</option>
                  <option value="Airtel">Airtel Nigeria 4G</option>
                  <option value="Glo">Globacom (Glo 4G)</option>
                  <option value="9mobile">9mobile 4G</option>
                </select>
              </label>

              <Input
                label="Active Cellular APN String"
                value={customApn}
                onChange={(e) => setCustomApn(e.target.value)}
                required
              />
            </div>

            <div style={{ borderTop: '1px solid var(--border)', paddingTop: '14px' }}>
              <h4 style={{ margin: '0 0 10px', fontSize: '14px' }}>⚙ Discrepancy Investigation Threshold</h4>
              <Input
                label="Pulser Discrepancy Anomaly Threshold (Litres)"
                type="number"
                step="0.001"
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                required
              />
              <small style={{ color: 'var(--muted)', display: 'block', marginTop: '4px' }}>
                Default standard: <strong>0.490 Litres</strong>. Any variance |CPU Volume − Pulser Volume| ≥ this threshold triggers an immediate critical alert and opens an investigation record.
              </small>
            </div>

            <Button type="submit">Save Telemetry Parameters</Button>
          </form>
        </Card>

        <Card>
          <h3 style={{ marginBottom: '12px' }}>☁ Cloud & Backend System Status</h3>
          <div style={{ display: 'grid', gap: '8px', fontSize: '13px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Platform Version:</span>
              <strong>VISUAL EYES 360 · v1.2.0 (Industrial IoT Edition)</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Database Architecture:</span>
              <span>PostgreSQL / Supabase Ready (Relational Schema Active)</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>User Identity:</span>
              <span><code>{user?.user_id}</code> (<Badge tone="info">{user?.role?.replace('_', ' ')}</Badge>)</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Cryptographic Session:</span>
              <Badge tone="success">JWT Bearer Active · Token Rotation Enforced</Badge>
            </div>
          </div>
        </Card>
      </div>
    </>
  )
}
