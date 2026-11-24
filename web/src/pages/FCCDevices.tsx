import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Badge, Button, Card, ErrorBanner, PageHeader } from '../components/ui'
import type { FCCDeviceItem } from '../types'

export default function FCCDevices() {
  const { can } = useAuth()
  const [devices, setDevices] = useState<FCCDeviceItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = () => {
    setLoading(true)
    api.get<FCCDeviceItem[]>('/fcc-devices')
      .then(setDevices)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load FCC devices'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const toggleOnline = async (id: string) => {
    try {
      await api.post(`/fcc-devices/${id}/toggle-online`)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to toggle status')
    }
  }

  return (
    <>
      <PageHeader
        title="Fuel Control Controllers (FCC)"
        subtitle="Hardware telemetry, wireless failover monitoring, and pulse calibration factors"
        action={<Button onClick={load} variant="secondary">↻ Refresh Telemetry</Button>}
      />
      {error && <ErrorBanner message={error} />}

      <div style={{ background: 'rgba(15, 111, 189, 0.08)', border: '1px solid var(--border)', padding: '12px 16px', borderRadius: '8px', marginBottom: '16px', fontSize: '13px' }}>
        <strong>Mandatory Networking Compliance:</strong> All FCC controllers communicate strictly via <strong>Wi-Fi 6</strong> or <strong>SIM Cellular (4G LTE Cat-1)</strong>. Ethernet physical wiring is excluded across all forecourt nodes.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '16px' }}>
        {devices.map((f) => (
          <Card key={f.id}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
              <div>
                <strong style={{ fontSize: '16px', fontFamily: 'monospace' }}>{f.device_uid}</strong>
                <div style={{ fontSize: '12px', color: 'var(--muted)' }}>
                  {f.station_name} · {f.dispenser_code} (Nozzle #{f.nozzle_number})
                </div>
              </div>
              <Badge tone={f.is_online ? 'success' : 'danger'}>
                {f.is_online ? '● ONLINE' : '○ OFFLINE'}
              </Badge>
            </div>

            <div style={{ background: 'var(--surface-2)', padding: '10px 12px', borderRadius: '8px', fontSize: '12px', display: 'grid', gap: '6px', margin: '10px 0' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Active WAN Link:</span>
                <span>
                  {f.connection_mode === 'WIFI' ? (
                    <strong style={{ color: 'var(--primary)' }}>📶 Wi-Fi (Primary)</strong>
                  ) : (
                    <strong style={{ color: 'var(--accent)' }}>📱 4G SIM LTE (Cellular)</strong>
                  )}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Wireless Signal Strength:</span>
                <span><strong>{f.signal_strength_dbm} dBm</strong> ({f.signal_strength_dbm > -70 ? 'Excellent' : 'Fair'})</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Pulser Calibration:</span>
                <span><strong>{f.calibration_factor}</strong> pulses/Litre</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Firmware Version:</span>
                <span><code>{f.firmware_version}</code></span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Last Heartbeat:</span>
                <small>{f.last_heartbeat ? new Date(f.last_heartbeat).toLocaleTimeString() : 'Never'}</small>
              </div>
            </div>

            {can('fcc_devices', 'manage') && (
              <Button
                variant={f.is_online ? 'secondary' : 'primary'}
                style={{ width: '100%' }}
                onClick={() => toggleOnline(f.id)}
              >
                {f.is_online ? 'Simulate Disconnect (Offline Mode)' : 'Restore Controller Connection'}
              </Button>
            )}
          </Card>
        ))}
      </div>
    </>
  )
}
