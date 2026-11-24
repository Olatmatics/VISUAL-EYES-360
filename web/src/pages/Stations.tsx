import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Badge, Button, Card, EmptyState, ErrorBanner, Input, Modal, PageHeader } from '../components/ui'
import { useGeo } from '../geo/GeoContext'
import type { Station } from '../types'

export default function Stations() {
  const { can } = useAuth()
  const { states, lgasFor, loadLgas } = useGeo()
  const [stations, setStations] = useState<Station[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [editing, setEditing] = useState<Station | null>(null)
  const emptyForm = {
    code: '', name: '', company_name: '', address: '', country: 'Nigeria',
    state_id: '', lga_id: '', city: '', gps_lat: '', gps_lng: '',
    manager_name: '', manager_phone: '', manager_email: '',
    supervisor_name: '', supervisor_phone: '', supervisor_email: '',
    phone: '', email: '', contact_person: '', notes: '', status: 'ACTIVE',
  }
  const [form, setForm] = useState(emptyForm)

  const load = () => {
    setLoading(true)
    api.get<Station[]>('/stations')
      .then(setStations)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load stations'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const openCreate = () => {
    setForm(emptyForm)
    setShowCreate(true)
  }

  const openEdit = (station: Station) => {
    setForm({
      code: station.code,
      name: station.name,
      company_name: station.company_name ?? '',
      address: station.address ?? '',
      country: station.country ?? 'Nigeria',
      state_id: station.state_id ?? '',
      lga_id: station.lga_id ?? '',
      city: station.city ?? '',
      gps_lat: station.gps_lat ?? '',
      gps_lng: station.gps_lng ?? '',
      manager_name: station.manager_name ?? '',
      manager_phone: station.manager_phone ?? '',
      manager_email: station.manager_email ?? '',
      supervisor_name: station.supervisor_name ?? '',
      supervisor_phone: station.supervisor_phone ?? '',
      supervisor_email: station.supervisor_email ?? '',
      phone: station.phone ?? '',
      email: station.email ?? '',
      contact_person: station.contact_person ?? '',
      notes: station.notes ?? '',
      status: station.status,
    })
    if (station.state_id) void loadLgas(station.state_id)
    setEditing(station)
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    try {
      if (editing) {
        await api.patch(`/stations/${editing.id}`, form)
      } else {
        await api.post('/stations', form)
      }
      setShowCreate(false)
      setEditing(null)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    }
  }

  const update = (key: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }))

  return (
    <>
      <PageHeader
        title="Stations"
        subtitle="Registered fuel stations within your authorized scope."
        action={can('stations', 'create') && <Button onClick={openCreate}>+ Register station</Button>}
      />
      {error && <ErrorBanner message={error} />}

      <Card>
        {loading ? (
          <div className="empty-state">Loading stations…</div>
        ) : stations.length === 0 ? (
          <EmptyState title="No stations" message="No stations are available in your assigned scope." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Code</th><th>Station</th><th>Location</th><th>Phone</th><th>Status</th><th>Registered</th>{can('stations', 'edit') && <th />}</tr>
              </thead>
              <tbody>
                {stations.map((station) => (
                  <tr key={station.id}>
                    <td><strong>{station.code}</strong></td>
                    <td>{station.name}</td>
                    <td>
                      {[station.city, station.lga_name, station.state_name].filter(Boolean).join(', ') || '—'}
                    </td>
                    <td>{station.phone || '—'}</td>
                    <td><Badge tone={station.status === 'ACTIVE' ? 'success' : 'warning'}>{station.status}</Badge></td>
                    <td>{new Date(station.registered_at).toLocaleDateString()}</td>
                    {can('stations', 'edit') && <td><Button variant="ghost" onClick={() => openEdit(station)}>Edit</Button></td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {(showCreate || editing) && (
        <Modal title={editing ? 'Edit station' : 'Register station'} onClose={() => { setShowCreate(false); setEditing(null) }}>
          <form className="modal-body" onSubmit={submit}>
            {!editing && <Input label="Station code" value={form.code} onChange={update('code')} required />}
            <Input label="Station name" value={form.name} onChange={update('name')} required />
            <div className="form-grid">
              <Input label="Company / organisation" value={form.company_name} onChange={update('company_name')} />
              <Input label="Country" value={form.country} onChange={update('country')} required />
            </div>
            <div className="form-grid">
              <label className="field">
                <span>State</span>
                <select
                  value={form.state_id}
                  onChange={(e) => {
                    const stateId = e.target.value
                    setForm((prev) => ({ ...prev, state_id: stateId, lga_id: '' }))
                    if (stateId) void loadLgas(stateId)
                  }}
                >
                  <option value="">Select state</option>
                  {states.map((state) => <option key={state.id} value={state.id}>{state.name}</option>)}
                </select>
              </label>
              <label className="field">
                <span>LGA</span>
                <select
                  value={form.lga_id}
                  onChange={(e) => setForm((prev) => ({ ...prev, lga_id: e.target.value }))}
                  disabled={!form.state_id}
                >
                  <option value="">Select LGA</option>
                  {lgasFor(form.state_id).map((lga) => <option key={lga.id} value={lga.id}>{lga.name}</option>)}
                </select>
              </label>
            </div>
            <div className="form-grid">
              <Input label="City / town" value={form.city} onChange={update('city')} />
              <label className="field">
                <span>Status</span>
                <select value={form.status} onChange={(e) => setForm((prev) => ({ ...prev, status: e.target.value }))}>
                  <option value="ACTIVE">Active</option>
                  <option value="INACTIVE">Inactive</option>
                  <option value="SUSPENDED">Suspended</option>
                  <option value="MAINTENANCE">Under Maintenance</option>
                  <option value="PENDING_APPROVAL">Pending Approval</option>
                </select>
              </label>
            </div>
            <Input label="Address" value={form.address} onChange={update('address')} />
            <div className="form-grid">
              <Input label="GPS latitude" value={form.gps_lat} onChange={update('gps_lat')} />
              <Input label="GPS longitude" value={form.gps_lng} onChange={update('gps_lng')} />
            </div>
            <div className="form-grid">
              <Input label="General phone" value={form.phone} onChange={update('phone')} />
              <Input label="General email" type="email" value={form.email} onChange={update('email')} />
            </div>
            <div className="form-grid">
              <Input label="Station manager" value={form.manager_name} onChange={update('manager_name')} />
              <Input label="Manager phone" value={form.manager_phone} onChange={update('manager_phone')} />
              <Input label="Manager email" type="email" value={form.manager_email} onChange={update('manager_email')} />
            </div>
            <div className="form-grid">
              <Input label="Station supervisor" value={form.supervisor_name} onChange={update('supervisor_name')} />
              <Input label="Supervisor phone" value={form.supervisor_phone} onChange={update('supervisor_phone')} />
              <Input label="Supervisor email" type="email" value={form.supervisor_email} onChange={update('supervisor_email')} />
            </div>
            {!editing && <Input label="Primary contact person" value={form.contact_person} onChange={update('contact_person')} />}
            <label className="field">
              <span>Additional notes</span>
              <textarea value={form.notes} onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))} />
            </label>
            <div className="modal-actions">
              <Button type="button" variant="secondary" onClick={() => { setShowCreate(false); setEditing(null) }}>Cancel</Button>
              <Button type="submit">{editing ? 'Save changes' : 'Register station'}</Button>
            </div>
          </form>
        </Modal>
      )}
    </>
  )
}
