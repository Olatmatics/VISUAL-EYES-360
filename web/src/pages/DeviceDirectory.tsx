import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api/client'
import { Badge, Button, Card, ErrorBanner, Input, PageHeader } from '../components/ui'
import type {
  DispenserItem,
  FCCDeviceItem,
  GeoLga,
  GeoState,
  NozzleItem,
  POSTerminalItem,
  Station,
  TankItem,
} from '../types'

type IdField = { label: string; value: string }
type Tone = 'success' | 'warning' | 'danger' | 'info' | 'neutral'
type Row = {
  id: string
  title: string
  subtitle: string
  ids: IdField[]
  badge?: { tone: Tone; text: string }
}
type Group = {
  key: string
  label: string
  icon: string
  note?: string
  rows: Row[]
}
type CardRow = {
  id: string
  uid: string
  owner: string
  blocked: boolean
  balance_ngn: number
  home_station?: string | null
  nationwide?: boolean
}

const TABS = [
  { key: 'all', label: 'All devices' },
  { key: 'stations', label: 'Stations' },
  { key: 'fcc', label: 'FCC controllers' },
  { key: 'tanks', label: 'Tanks' },
  { key: 'pumps', label: 'Pumps' },
  { key: 'nozzles', label: 'Nozzles' },
  { key: 'pos', label: 'OPay POS' },
  { key: 'rfid', label: 'RFID cards' },
]

const text = (value: unknown) => (value === undefined || value === null ? '' : String(value))

function idFields(values: Array<[string, unknown]>): IdField[] {
  return values
    .map(([label, value]) => ({ label, value: text(value) }))
    .filter((field) => field.value.length > 0)
}

function IdChip({ field, copied, onCopy }: {
  field: IdField
  copied: string
  onCopy: (field: IdField) => void
}) {
  const key = `${field.label}:${field.value}`
  return (
    <button
      type="button"
      className={`id-chip ${copied === key ? 'copied' : ''}`}
      onClick={() => onCopy(field)}
      title={`Copy ${field.label}`}
    >
      <span className="id-chip-label">{field.label}</span>
      <code>{field.value}</code>
      <span className="id-chip-action">{copied === key ? '✓ Copied' : '⧉'}</span>
    </button>
  )
}

export default function DeviceDirectory() {
  const [states, setStates] = useState<GeoState[]>([])
  const [lgas, setLgas] = useState<GeoLga[]>([])
  const [stations, setStations] = useState<Station[]>([])
  const [stateId, setStateId] = useState('')
  const [lgaId, setLgaId] = useState('')
  const [stationId, setStationId] = useState('')
  const [search, setSearch] = useState('')
  const [tab, setTab] = useState('all')
  const [loading, setLoading] = useState(true)
  const [refreshKey, setRefreshKey] = useState(0)
  const [copied, setCopied] = useState('')
  const [warnings, setWarnings] = useState<string[]>([])
  const [data, setData] = useState<{
    fcc: FCCDeviceItem[]
    tanks: TankItem[]
    pumps: DispenserItem[]
    nozzles: NozzleItem[]
    pos: POSTerminalItem[]
    cards: CardRow[]
  }>({ fcc: [], tanks: [], pumps: [], nozzles: [], pos: [], cards: [] })
  const requestSeq = useRef(0)

  useEffect(() => {
    api.get<GeoState[]>('/geo/states').then(setStates).catch(() => setStates([]))
  }, [])

  useEffect(() => {
    if (!stateId) {
      setLgas([])
      setLgaId('')
      return
    }
    api.get<GeoLga[]>(`/geo/states/${stateId}/lgas`).then(setLgas).catch(() => setLgas([]))
  }, [stateId])

  useEffect(() => {
    const params = new URLSearchParams()
    if (stateId) params.set('state_id', stateId)
    if (lgaId) params.set('lga_id', lgaId)
    const query = params.toString() ? `?${params.toString()}` : ''
    api.get<Station[]>(`/stations${query}`).then((rows) => {
      setStations(rows)
      if (stationId && !rows.some((row) => row.id === stationId)) setStationId('')
    }).catch(() => setStations([]))
  }, [stateId, lgaId, refreshKey, stationId])

  useEffect(() => {
    const seq = ++requestSeq.current
    setLoading(true)
    setWarnings([])
    const stationQuery = stationId ? `?station_id=${stationId}` : ''

    const sources = [
      { label: 'FCC controllers', path: `/fcc-devices${stationQuery}` },
      { label: 'Tanks', path: `/tanks${stationQuery}` },
      { label: 'Pumps', path: `/dispensers${stationQuery}` },
      { label: 'Nozzles', path: `/nozzles${stationQuery}` },
      { label: 'OPay POS terminals', path: `/payments/terminals${stationQuery}` },
      { label: 'RFID cards', path: '/rfid/cards' },
    ]

    Promise.allSettled(sources.map((source) => api.get<unknown[]>(source.path))).then((results) => {
      if (seq !== requestSeq.current) return
      const nextWarnings: string[] = []
      const next = { fcc: [], tanks: [], pumps: [], nozzles: [], pos: [], cards: [] } as typeof data
      results.forEach((result, index) => {
        if (result.status === 'fulfilled') {
          const rows = result.value
          if (index === 0) next.fcc = rows as FCCDeviceItem[]
          if (index === 1) next.tanks = rows as TankItem[]
          if (index === 2) next.pumps = rows as DispenserItem[]
          if (index === 3) next.nozzles = rows as NozzleItem[]
          if (index === 4) next.pos = rows as POSTerminalItem[]
          if (index === 5) next.cards = rows as CardRow[]
        } else {
          const reason = result.reason
          const message = reason instanceof Error ? reason.message : 'could not be loaded'
          nextWarnings.push(`${sources[index].label}: ${message}`)
        }
      })
      setData(next)
      setWarnings(nextWarnings)
      setLoading(false)
    })
  }, [stationId, refreshKey])

  const copyValue = async (field: IdField) => {
    const key = `${field.label}:${field.value}`
    let ok = false
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(field.value)
        ok = true
      }
    } catch {
      // Fall back for non-secure LAN addresses.
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
    setCopied(ok ? key : '')
    window.setTimeout(() => setCopied((current) => (current === key ? '' : current)), 1600)
  }

  const inScope = (rowStationId?: string | null) => {
    if (stationId) return rowStationId === stationId
    if (stateId || lgaId) return Boolean(rowStationId && stations.some((station) => station.id === rowStationId))
    return true
  }

  const groups = useMemo<Group[]>(() => {
    const query = search.trim().toLowerCase()
    const visible = (row: Row) => !query || [row.title, row.subtitle, ...row.ids.map((field) => field.value)]
      .join(' ')
      .toLowerCase()
      .includes(query)

    const stationRows: Row[] = stations.filter((station) => inScope(station.id)).map((station) => ({
      id: station.id,
      title: station.name,
      subtitle: [station.code, station.state_name, station.lga_name, station.city].filter(Boolean).join(' · '),
      ids: idFields([
        ['Station ID', station.id],
        ['Station code', station.code],
        ['State ID', station.state_id],
        ['LGA ID', station.lga_id],
      ]),
      badge: { tone: station.status === 'ACTIVE' ? 'success' : 'warning', text: station.status },
    }))

    const fccRows: Row[] = data.fcc.filter((fcc) => inScope(fcc.station_id)).map((fcc) => ({
      id: fcc.id,
      title: fcc.device_uid,
      subtitle: [fcc.station_name, fcc.dispenser_code, `Nozzle #${text(fcc.nozzle_number) || '—'}`].filter(Boolean).join(' · '),
      ids: idFields([
        ['Device UID (sketch)', fcc.device_uid],
        ['FCC record ID', fcc.id],
        ['Nozzle ID', fcc.nozzle_id],
        ['Dispenser ID', fcc.dispenser_id],
        ['Station ID', fcc.station_id],
        ['POS terminal ID', (fcc as unknown as { pos_terminal?: string }).pos_terminal || fcc.pos_terminal_id],
      ]),
      badge: { tone: fcc.is_online ? 'success' : 'danger', text: fcc.is_online ? 'ONLINE' : 'OFFLINE' },
    }))

    const tankRows: Row[] = data.tanks.filter((tank) => inScope(tank.station_id)).map((tank) => ({
      id: tank.id,
      title: [tank.code, tank.name].filter(Boolean).join(' · '),
      subtitle: `${tank.station_name} · ${tank.product_name} · ${tank.capacity_l.toLocaleString()} L`,
      ids: idFields([
        ['Tank ID (sketch)', tank.id],
        ['Tank code', tank.code],
        ['Controller UID (sketch)', tank.controller?.device_uid],
        ['Controller ID', tank.controller?.id],
        ['Station ID', tank.station_id],
        ['Product', tank.product_code],
      ]),
      badge: tank.hatch_open
        ? { tone: 'danger', text: 'HATCH OPEN' }
        : { tone: 'success', text: 'HATCH SECURE' },
    }))

    const pumpRows: Row[] = data.pumps.filter((pump) => inScope(pump.station_id)).map((pump) => ({
      id: pump.id,
      title: [pump.code, pump.name || pump.model].filter(Boolean).join(' · '),
      subtitle: `${pump.station_name} · ${pump.nozzles?.length || 0} nozzle(s) · S/N ${pump.serial || '—'}`,
      ids: idFields([
        ['Dispenser ID', pump.id],
        ['Pump code', pump.code],
        ['Serial number', pump.serial],
        ['Station ID', pump.station_id],
      ]),
      badge: { tone: pump.status === 'ACTIVE' ? 'success' : 'warning', text: pump.status },
    }))

    const nozzleRows: Row[] = data.nozzles.filter((nozzle) => inScope(nozzle.station_id)).map((nozzle) => ({
      id: nozzle.id,
      title: `Nozzle ${nozzle.number} · ${nozzle.dispenser_code}`,
      subtitle: `${nozzle.station_name} · ₦${nozzle.price}/L`,
      ids: idFields([
        ['Nozzle ID (sketch)', nozzle.id],
        ['Dispenser ID', nozzle.dispenser_id],
        ['Tank ID', nozzle.tank_id],
        ['FCC UID (sketch)', nozzle.fcc?.uid],
        ['FCC record ID', nozzle.fcc?.id],
        ['Station ID', nozzle.station_id],
      ]),
      badge: { tone: 'info', text: `₦${nozzle.price}/L` },
    }))

    const posRows: Row[] = data.pos.filter((pos) => inScope(pos.station_id)).map((pos) => ({
      id: pos.id,
      title: `Terminal ${pos.terminal_id}`,
      subtitle: `${pos.station_name} · ${pos.dispenser_code ? `Assigned to ${pos.dispenser_code}` : 'Not assigned to a nozzle'}`,
      ids: idFields([
        ['Terminal record ID', pos.id],
        ['Terminal ID (sketch POS_SN)', pos.terminal_id],
        ['Serial number', pos.serial_number],
        ['Station ID', pos.station_id],
        ['Nozzle ID', pos.nozzle_id],
      ]),
      badge: { tone: pos.is_active ? 'success' : 'warning', text: pos.is_active ? 'ACTIVE' : 'INACTIVE' },
    }))

    const cardRows: Row[] = data.cards.map((card) => ({
      id: card.id,
      title: card.uid,
      subtitle: `${card.owner} · ₦${card.balance_ngn.toLocaleString()} · Nationwide${card.home_station ? ` · registered at ${card.home_station}` : ''}`,
      ids: idFields([
        ['Card record ID', card.id],
        ['Card UID (sketch)', card.uid],
        ['Home station (registration only)', card.home_station || 'not set'],
      ]),
      badge: { tone: card.blocked ? 'danger' : 'success', text: card.blocked ? 'BLOCKED' : 'ACTIVE' },
    }))

    return [
      { key: 'stations', label: 'Stations', icon: '◈', rows: stationRows },
      { key: 'fcc', label: 'FCC Controllers', icon: '📡', note: 'Use Device UID in the FCC sketch. Use Nozzle ID for NOZZLE_A_ID / NOZZLE_B_ID.', rows: fccRows },
      { key: 'tanks', label: 'Tanks & Tank Controllers', icon: '🛢', note: 'Use Tank ID in the tank monitor sketch. Controller UID is the device identity for tank telemetry.', rows: tankRows },
      { key: 'pumps', label: 'Dispensers / Pumps', icon: '⛽', rows: pumpRows },
      { key: 'nozzles', label: 'Nozzles', icon: '🔫', note: 'Use Nozzle ID in the FCC or RFID sketch and for POS assignment.', rows: nozzleRows },
      { key: 'pos', label: 'OPay POS Terminals', icon: '💳', note: 'Use Terminal ID as POS_SN in the FCC sketch.', rows: posRows },
      { key: 'rfid', label: 'RFID Cards', icon: '🪪', note: 'Cards are nationwide and are not tied to a state or station.', rows: cardRows },
    ]
      .map((group) => ({ ...group, rows: group.rows.filter(visible) }))
  }, [data, stations, stateId, lgaId, stationId, search])

  const shownGroups = tab === 'all' ? groups : groups.filter((group) => group.key === tab)
  const totalRows = groups.reduce((sum, group) => sum + group.rows.length, 0)

  return (
    <>
      <PageHeader
        title="Device ID Directory"
        subtitle="Find every registered device and copy the exact ID or UID needed for your ESP32 sketch."
        action={<Button variant="secondary" onClick={() => setRefreshKey((key) => key + 1)} disabled={loading}>
          {loading ? 'Loading…' : '↻ Refresh'}
        </Button>}
      />

      <Card style={{ marginBottom: 16 }}>
        <div className="directory-filters">
          <label className="field">
            <span>1. State / FCT</span>
            <select value={stateId} onChange={(event) => {
              setStateId(event.target.value)
              setLgaId('')
              setStationId('')
            }}>
              <option value="">All states ({states.length})</option>
              {states.map((state) => <option key={state.id} value={state.id}>{state.name}</option>)}
            </select>
          </label>
          <label className="field">
            <span>2. Local Government Area</span>
            <select value={lgaId} disabled={!stateId} onChange={(event) => {
              setLgaId(event.target.value)
              setStationId('')
            }}>
              <option value="">All LGAs in this state</option>
              {lgas.map((lga) => <option key={lga.id} value={lga.id}>{lga.name}</option>)}
            </select>
          </label>
          <label className="field">
            <span>3. Station</span>
            <select value={stationId} onChange={(event) => setStationId(event.target.value)}>
              <option value="">All stations ({stations.length})</option>
              {stations.map((station) => (
                <option key={station.id} value={station.id}>{station.name} ({station.code})</option>
              ))}
            </select>
          </label>
          <Input
            label="Search ID, UID, code or owner"
            placeholder="e.g. FCC-DEV-A or TK-0001"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <p className="muted" style={{ fontSize: 12, marginTop: 10, marginBottom: 0 }}>
          RFID cards always appear because they work nationwide. State and LGA filters apply to stations and their equipment.
        </p>
      </Card>

      {warnings.length > 0 && <ErrorBanner message={`Some lists could not be loaded — ${warnings.join(' | ')}`} />}

      <Card style={{ marginBottom: 16 }}>
        <h3>Which ID goes where?</h3>
        <div className="directory-help">
          <div className="directory-help-row"><span>FCC sketch <code>DEVICE_UID_A/B</code></span><strong>FCC Device UID</strong></div>
          <div className="directory-help-row"><span>FCC sketch <code>NOZZLE_A_ID/B</code></span><strong>Nozzle ID</strong></div>
          <div className="directory-help-row"><span>FCC sketch <code>POS_SN</code></span><strong>OPay Terminal ID</strong></div>
          <div className="directory-help-row"><span>Tank sketch <code>TANK_ID</code></span><strong>Tank ID</strong></div>
          <div className="directory-help-row"><span>RFID sketch <code>NOZZLE_ID</code></span><strong>Nozzle ID</strong></div>
        </div>
      </Card>

      <div className="directory-tabs">
        {TABS.map((item) => {
          const count = item.key === 'all'
            ? totalRows
            : groups.find((group) => group.key === item.key)?.rows.length || 0
          return (
            <Button key={item.key} variant={tab === item.key ? 'primary' : 'secondary'} onClick={() => setTab(item.key)}>
              {item.label} <Badge tone="neutral">{count}</Badge>
            </Button>
          )
        })}
      </div>

      {loading && <div className="empty-state">Loading registered devices…</div>}

      {!loading && shownGroups.map((group) => (
        <Card key={group.key} style={{ marginBottom: 16 }}>
          <div className="directory-head">
            <span className="directory-icon">{group.icon}</span>
            <div>
              <h3>{group.label} <Badge tone="neutral">{group.rows.length}</Badge></h3>
              {group.note && <small>{group.note}</small>}
            </div>
          </div>
          {group.rows.length === 0 ? (
            <div className="empty-state">No {group.label.toLowerCase()} match this location or search.</div>
          ) : (
            <div className="directory-rows">
              {group.rows.map((row) => (
                <div key={`${group.key}-${row.id}`} className="device-row">
                  <div className="device-row-head">
                    <div>
                      <div className="device-row-title">{row.title}</div>
                      <div className="device-row-sub">{row.subtitle || '—'}</div>
                    </div>
                    {row.badge && <Badge tone={row.badge.tone}>{row.badge.text}</Badge>}
                  </div>
                  <div className="id-chips">
                    {row.ids.map((field) => (
                      <IdChip key={`${field.label}-${field.value}`} field={field} copied={copied} onCopy={copyValue} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      ))}
    </>
  )
}
