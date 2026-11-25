import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { Badge, Button, Card, ErrorBanner, Input, PageHeader } from '../components/ui'

type Option = { id: string; name?: string; code?: string; number?: number; dispenser_code?: string; price?: number }

type Options = {
  stations: Option[]
  free_nozzles: Option[]
  tanks: Option[]
}

export default function QuickSetup() {
  const [options, setOptions] = useState<Options>({ stations: [], free_nozzles: [], tanks: [] })
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [stationName, setStationName] = useState('')
  const [stationId, setStationId] = useState('')
  const [pumpConfig, setPumpConfig] = useState('DOUBLE')
  const [pumpPrice, setPumpPrice] = useState('1000')
  const [tankCapacity, setTankCapacity] = useState('30000')
  const [fccUid, setFccUid] = useState('')
  const [fccStation, setFccStation] = useState('')
  const [rfidUid, setRfidUid] = useState('')
  const [rfidName, setRfidName] = useState('')
  const [rfidAmount, setRfidAmount] = useState('5000')

  const load = () => api.get<Options>('/quick/options')
    .then((o) => {
      setOptions(o)
      if (!stationId && o.stations.length) { setStationId(o.stations[0].id); setFccStation(o.stations[0].id) }
    })
    .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load options'))

  useEffect(() => { load() }, [])

  const run = async (path: string, body: object, ok: (r: any) => string) => {
    setError(''); setMessage('')
    try { setMessage(ok(await api.post(path, body))); load() }
    catch (e) { setError(e instanceof Error ? e.message : 'Request failed') }
  }

  return (
    <>
      <PageHeader title="Quick Setup" subtitle="Register only what is essential. IDs and codes are generated automatically." />
      {error && <ErrorBanner message={error} />}
      {message && <div className="notice-success">{message}</div>}

      <div className="quick-grid">
        <Card>
          <h3>1 · Station</h3>
          <p className="muted">Only a name is needed.</p>
          <Input label="Station name" value={stationName} onChange={(e) => setStationName(e.target.value)} placeholder="e.g. Abuja Main" required />
          <Button onClick={() => { void run('/quick/station', { name: stationName }, (r) => `Station ${r.code} created.`); setStationName('') }}>Register station</Button>
        </Card>

        <Card>
          <h3>2 · Pump / Dispenser</h3>
          <p className="muted"> Creates the nozzle records for you.</p>
          <label className="field"><span>Station</span>
            <select value={stationId} onChange={(e) => setStationId(e.target.value)}>
              <option value="">Select station</option>
              {options.stations.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.code})</option>)}
            </select>
          </label>
          <label className="field"><span>Nozzles</span>
            <select value={pumpConfig} onChange={(e) => setPumpConfig(e.target.value)}>
              <option value="SINGLE">Single</option>
              <option value="DOUBLE">Double</option>
            </select>
          </label>
          <Input label="Price per litre (₦)" type="number" value={pumpPrice} onChange={(e) => setPumpPrice(e.target.value)} />
          <Button onClick={() => run('/quick/pump', { station_id: stationId, nozzle_config: pumpConfig, price: Number(pumpPrice) }, (r) => `Pump ${r.code} created with ${r.nozzles.length} nozzle(s).`)}>Register pump</Button>
        </Card>

        <Card>
          <h3>3 · Tank</h3>
          <label className="field"><span>Station</span>
            <select value={stationId} onChange={(e) => setStationId(e.target.value)}>
              {options.stations.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
          <Input label="Capacity (litres)" type="number" value={tankCapacity} onChange={(e) => setTankCapacity(e.target.value)} />
          <Button onClick={() => run('/quick/tank', { station_id: stationId, capacity_l: Number(tankCapacity) }, (r) => `Tank ${r.code} created.`)}>Register tank</Button>
        </Card>

        <Card>
          <h3>4 · FCC Controller</h3>
          <p className="muted">UID from your ESP32 sketch. A free nozzle is assigned automatically.</p>
          <Input label="Controller UID" value={fccUid} onChange={(e) => setFccUid(e.target.value)} placeholder="FCC-DEV-A" />
          <label className="field"><span>Station</span>
            <select value={fccStation} onChange={(e) => setFccStation(e.target.value)}>
              {options.stations.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
          <Button onClick={() => run('/quick/fcc', { device_uid: fccUid, station_id: fccStation }, (r) => `FCC ${r.device_uid} registered on nozzle ${r.nozzle_id}.`)}>Register FCC</Button>
          <small className="muted">Free nozzles available: {options.free_nozzles.length}</small>
        </Card>

        <Card>
          <h3>5 · RFID card</h3>
          <p className="muted">Place a card on the reader and type its UID in Serial Monitor, or enter it here.</p>
          <Input label="Card UID" value={rfidUid} onChange={(e) => setRfidUid(e.target.value)} placeholder="Card UID" />
          <Input label="Owner name (optional)" value={rfidName} onChange={(e) => setRfidName(e.target.value)} />
          <Button variant="secondary" onClick={() => run('/rfid/scan', { uid: rfidUid, name: rfidName }, (r) => r.message + ' — balance ₦' + r.balance_ngn)}>Scan / register card</Button>
          <Input label="Fund wallet (₦)" type="number" value={rfidAmount} onChange={(e) => setRfidAmount(e.target.value)} />
          <Button variant="secondary" onClick={() => run('/rfid/fund', { uid: rfidUid, amount_ngn: Number(rfidAmount) }, (r) => `Wallet funded. Balance ₦${r.balance_ngn}`)}>Fund card</Button>
        </Card>
      </div>
    </>
  )
}
