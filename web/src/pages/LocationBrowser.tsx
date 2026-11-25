import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { Badge, Button, Card, ErrorBanner, PageHeader } from '../components/ui'
import type { GeoLga, GeoState, Station } from '../types'

type Item = Record<string, any>

type CardItem = { id: string; uid: string; owner: string; blocked: boolean; balance_ngn: number }

export default function LocationBrowser() {
  const navigate = useNavigate()
  const [states, setStates] = useState<GeoState[]>([])
  const [lgas, setLgas] = useState<GeoLga[]>([])
  const [stations, setStations] = useState<Station[]>([])
  const [stateId, setStateId] = useState('')
  const [lgaId, setLgaId] = useState('')
  const [stationId, setStationId] = useState('')
  const [tab, setTab] = useState<'fcc' | 'tanks' | 'pumps' | 'nozzles' | 'cards'>('fcc')
  const [items, setItems] = useState<Item[]>([])
  const [cards, setCards] = useState<CardItem[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    api.get<GeoState[]>('/geo/states').then(setStates).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!stateId) { setLgas([]); setLgaId(''); return }
    api.get<GeoLga[]>(`/geo/states/${stateId}/lgas`).then(setLgas).catch(() => setLgas([]))
  }, [stateId])

  useEffect(() => {
    if (!stateId) { setStations([]); setStationId(''); return }
    const q = new URLSearchParams({ state_id: stateId })
    if (lgaId) q.set('lga_id', lgaId)
    api.get<Station[]>(`/stations?${q}`).then((s) => {
      setStations(s)
      if (!s.some((x) => x.id === stationId)) setStationId(s[0]?.id || '')
    }).catch(() => setStations([]))
  }, [stateId, lgaId])

  useEffect(() => {
    if (tab === 'cards') {
      api.get<CardItem[]>('/rfid/cards').then(setCards).catch((e) => setError(e.message))
      return
    }
    const map = {
      fcc: '/fcc-devices', tanks: '/tanks', pumps: '/dispensers', nozzles: '/nozzles',
    }
    const q = stationId ? `?station_id=${stationId}` : ''
    api.get<Item[]>(`${map[tab]}${q}`).then(setItems).catch((e) => setError(e.message))
  }, [tab, stationId])

  return (
    <>
      <PageHeader
        title="Browse by Location"
        subtitle="Country → State → LGA → Station → Equipment. RFID cards work in every location."
        action={<Button variant="secondary" onClick={() => navigate('/device-directory')}>🪪 Device ID Directory</Button>}
      />
      {error && <ErrorBanner message={error} />}

      <Card style={{ marginBottom: 16 }}>
        <div className="form-grid">
          <label className="field"><span>1. State / FCT</span>
            <select value={stateId} onChange={(e) => { setStateId(e.target.value); setLgaId(''); setStationId('') }}>
              <option value="">All states ({states.length})</option>
              {states.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
          <label className="field"><span>2. Local Government Area</span>
            <select value={lgaId} disabled={!stateId} onChange={(e) => { setLgaId(e.target.value); setStationId('') }}>
              <option value="">All LGAs in this state</option>
              {lgas.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          </label>
          <label className="field"><span>3. Station</span>
            <select value={stationId} disabled={!stateId} onChange={(e) => setStationId(e.target.value)}>
              <option value="">All stations in this area</option>
              {stations.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.code})</option>)}
            </select>
          </label>
        </div>
      </Card>

      <Card>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
          {(['fcc', 'tanks', 'pumps', 'nozzles', 'cards'] as const).map((t) => (
            <Button key={t} variant={tab === t ? 'primary' : 'secondary'}
              onClick={() => setTab(t)}>
              {t === 'fcc' ? 'FCC Controllers' : t === 'cards' ? 'RFID Cards' : t.toUpperCase()}
            </Button>
          ))}
        </div>

        {tab === 'cards' ? (
          <>
            <p className="muted" style={{ fontSize: 13 }}>
              Cards are valid <strong>nationwide</strong> — a card registered in Abuja works in Ibadan.
            </p>
            <div className="inventory-grid">
              {cards.map((c) => <div key={c.id} className="inventory-item">
                <strong><code>{c.uid}</code></strong>
                <div>{c.owner}</div>
                <div>Balance ₦{c.balance_ngn.toLocaleString()}</div>
                <Badge tone={c.blocked ? 'danger' : 'success'}>{c.blocked ? 'BLOCKED' : 'ACTIVE'}</Badge>
              </div>)}
              {cards.length === 0 && <div className="empty-state">No cards registered yet.</div>}
            </div>
          </>
        ) : (
          <div className="inventory-grid">
            {items.map((x, i) => <div key={x.id || i} className="inventory-item">
              <strong>{x.device_uid || x.code || x.name || x.label || `Item ${i + 1}`}</strong>
              <div>{x.station_name || ''}</div>
              {x.status && <Badge tone={x.status === 'ACTIVE' || x.is_online ? 'success' : 'warning'}>{x.status}</Badge>}
              {x.is_online !== undefined && <div>{x.is_online ? '● Online' : '○ Offline'}</div>}
              {x.price !== undefined && <div>₦{x.price}/L</div>}
              {x.current_volume_l !== undefined && <div>{x.current_volume_l.toLocaleString()} L</div>}
            </div>)}
            {items.length === 0 && <div className="empty-state">Nothing registered here yet.</div>}
          </div>
        )}
      </Card>
    </>
  )
}
