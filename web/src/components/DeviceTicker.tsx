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

  if (devices.length === 0) return null
  const online = devices.filter((d) => d.online).length
  const line = devices.map((d) => {
    const place = [d.lga, d.state].filter(Boolean).join(', ') || d.station
    return `${d.kind} ${d.uid} · ${d.station} (${place}) · ${d.online ? 'ONLINE' : 'OFFLINE'}`
  }).join('   ◆   ')

  return (
    <div className="device-ticker" title={`${online}/${devices.length} controllers online`}>
      <span className="ticker-label">● {online}/{devices.length} ONLINE</span>
      <div className="ticker-window">
        <div className="ticker-track">{line} &nbsp;&nbsp; ◆ &nbsp;&nbsp; {line}</div>
      </div>
    </div>
  )
}
