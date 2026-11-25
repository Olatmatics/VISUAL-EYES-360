import { useEffect, useState } from 'react'
import { api } from '../api/client'

type Device = {
  kind: string
  uid: string
  station: string
  state: string
  lga: string
  online: boolean
  last_seen: string | null
}

export default function DeviceTicker() {
  const [devices, setDevices] = useState<Device[]>([])

  useEffect(() => {
    const load = () => api.get<Device[]>('/simple/connected').then(setDevices).catch(() => {})
    load()
    const timer = window.setInterval(load, 15000)
    return () => window.clearInterval(timer)
  }, [])

  const onlineDevices = devices.filter((d) => d.online)
  const line = onlineDevices.map((d) => {
    const place = [d.lga, d.state].filter(Boolean).join(', ') || d.station
    return `${d.kind} ${d.uid} · ${d.station} (${place}) · ONLINE`
  }).join('   ◆   ')

  return (
    <div className="device-ticker" title={`${onlineDevices.length} controller(s) online`}>
      <span className="ticker-label">● {onlineDevices.length} ONLINE</span>
      <div className="ticker-window">
        <div className="ticker-track">
          {onlineDevices.length ? `${line}   ◆   ${line}` : 'No controllers online'}
        </div>
      </div>
    </div>
  )
}
