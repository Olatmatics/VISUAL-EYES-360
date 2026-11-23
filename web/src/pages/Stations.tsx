import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Badge, Button, Card, EmptyState, ErrorBanner, Input, Modal, PageHeader } from '../components/ui'
import type { Station } from '../types'

export default function Stations() {
  const { can } = useAuth()
  const [stations, setStations] = useState<Station[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [editing, setEditing] = useState<Station | null>(null)
  const [form, setForm] = useState({ code: '', name: '', address: '', city: '', phone: '', contact_person: '' })

  const load = () => {
    setLoading(true)
    api.get<Station[]>('/stations')
      .then(setStations)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load stations'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const openCreate = () => {
    setForm({ code: '', name: '', address: '', city: '', phone: '', contact_person: '' })
    setShowCreate(true)
  }

  const openEdit = (station: Station) => {
    setForm({
      code: station.code,
      name: station.name,
      address: station.address ?? '',
      city: station.city ?? '',
      phone: station.phone ?? '',
      contact_person: '',
    })
    setEditing(station)
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    try {
      if (editing) {
        await api.patch(`/stations/${editing.id}`, {
          name: form.name, address: form.address, city: form.city, phone: form.phone,
        })
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
                    <td>{station.city || '—'}</td>
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
              <Input label="City / town" value={form.city} onChange={update('city')} />
              <Input label="Phone" value={form.phone} onChange={update('phone')} />
            </div>
            <Input label="Address" value={form.address} onChange={update('address')} />
            {!editing && <Input label="Contact person" value={form.contact_person} onChange={update('contact_person')} />}
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
