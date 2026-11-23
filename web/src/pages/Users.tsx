import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Badge, Button, Card, EmptyState, ErrorBanner, Input, Modal, PageHeader } from '../components/ui'
import type { Manager, PermissionModule, Station } from '../types'

type FormState = {
  full_name: string
  manager_id: string
  password: string
  confirm_password: string
  phone: string
  email: string
  station_ids: string[]
  all_stations: boolean
  is_active: boolean
  selected: Record<string, boolean>
}

const emptyForm = (): FormState => ({
  full_name: '', manager_id: '', password: '', confirm_password: '', phone: '', email: '',
  station_ids: [], all_stations: false, is_active: true, selected: {},
})

export default function Users() {
  const { user } = useAuth()
  const [managers, setManagers] = useState<Manager[]>([])
  const [modules, setModules] = useState<PermissionModule[]>([])
  const [stations, setStations] = useState<Station[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState<Manager | null>(null)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState<FormState>(emptyForm())
  const [resetTarget, setResetTarget] = useState<Manager | null>(null)
  const [newPassword, setNewPassword] = useState('')
  const [openModule, setOpenModule] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    Promise.all([
      api.get<Manager[]>('/users'),
      api.get<PermissionModule[]>('/permissions/catalogue'),
      api.get<Station[]>('/stations'),
    ])
      .then(([m, p, s]) => { setManagers(m); setModules(p); setStations(s) })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load users'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const openCreate = () => {
    setForm(emptyForm())
    setCreating(true)
    setEditing(null)
  }

  const openEdit = (manager: Manager) => {
    const selected: Record<string, boolean> = {}
    manager.permissions.forEach((key) => { selected[key] = true })
    setForm({
      full_name: manager.full_name,
      manager_id: manager.user_id,
      password: '', confirm_password: '', phone: manager.phone ?? '', email: manager.email ?? '',
      station_ids: manager.station_ids,
      all_stations: manager.all_stations,
      is_active: manager.is_active,
      selected,
    })
    setEditing(manager)
    setCreating(false)
  }

  const togglePermission = (key: string) =>
    setForm((prev) => ({ ...prev, selected: { ...prev.selected, [key]: !prev.selected[key] } }))

  const toggleStation = (id: string) =>
    setForm((prev) => ({
      ...prev,
      station_ids: prev.station_ids.includes(id) ? prev.station_ids.filter((s) => s !== id) : [...prev.station_ids, id],
    }))

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    const permissions = Object.entries(form.selected)
      .filter(([, checked]) => checked)
      .map(([key]) => {
        const [module, action] = key.split(':')
        return { module, action, effect: 'GRANT' }
      })
    try {
      if (editing) {
        await api.patch(`/users/${editing.id}`, {
          full_name: form.full_name, phone: form.phone, email: form.email,
          station_ids: form.station_ids, all_stations: form.all_stations,
          is_active: form.is_active, permissions,
        })
      } else {
        await api.post('/users/managers', {
          full_name: form.full_name, manager_id: form.manager_id,
          password: form.password, confirm_password: form.confirm_password,
          phone: form.phone, email: form.email, station_ids: form.station_ids,
          all_stations: form.all_stations, is_active: form.is_active, permissions,
        })
      }
      setCreating(false)
      setEditing(null)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    }
  }

  const setStatus = async (manager: Manager, active: boolean) => {
    try {
      await api.post(`/users/${manager.id}/status`, { is_active: active, reason: active ? 'Reinstated' : 'Suspended by administrator' })
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Status update failed')
    }
  }

  const submitReset = async () => {
    if (!resetTarget) return
    try {
      await api.post(`/users/${resetTarget.id}/password/reset`, { new_password: newPassword })
      setResetTarget(null)
      setNewPassword('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Password reset failed')
    }
  }

  return (
    <>
      <PageHeader
        title="User Management"
        subtitle="Create Managers, assign stations and configure exact module permissions."
        action={<Button onClick={openCreate}>+ Create Manager</Button>}
      />
      <div className="notice compact">
        Signed in as <strong>{user?.full_name}</strong> ({user?.role?.replace('_', ' ')}). Only the Superior Administrator can manage accounts.
      </div>
      {error && <ErrorBanner message={error} />}

      <Card>
        {loading ? (
          <div className="empty-state">Loading accounts…</div>
        ) : managers.length === 0 ? (
          <EmptyState title="No managers" message="Create a Manager account to delegate station operations." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Manager</th><th>User ID</th><th>Stations</th><th>Permissions</th><th>Status</th><th>Last login</th><th>Actions</th></tr>
              </thead>
              <tbody>
                {managers.map((manager) => (
                  <tr key={manager.id}>
                    <td><strong>{manager.full_name}</strong><br /><small>{manager.email || manager.phone || '—'}</small></td>
                    <td><code>{manager.user_id}</code></td>
                    <td>{manager.all_stations ? 'All authorized' : manager.station_ids.length}</td>
                    <td>{manager.permissions.length}</td>
                    <td><Badge tone={manager.is_active ? 'success' : 'danger'}>{manager.is_active ? 'Active' : 'Inactive'}</Badge></td>
                    <td>{manager.last_login_at ? new Date(manager.last_login_at).toLocaleString() : 'Never'}</td>
                    <td>
                      <div className="row-actions">
                        <Button variant="ghost" onClick={() => openEdit(manager)}>Edit</Button>
                        <Button variant="ghost" onClick={() => { setResetTarget(manager); setNewPassword('') }}>Reset</Button>
                        <Button variant="ghost" onClick={() => setStatus(manager, !manager.is_active)}>
                          {manager.is_active ? 'Suspend' : 'Activate'}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {(creating || editing) && (
        <Modal title={editing ? `Edit ${editing.full_name}` : 'Create Manager'} onClose={() => { setCreating(false); setEditing(null) }}>
          <form className="modal-body" onSubmit={submit}>
            <div className="form-grid">
              <Input label="Full name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
              <Input label="Manager ID" value={form.manager_id} disabled={!!editing} onChange={(e) => setForm({ ...form, manager_id: e.target.value })} required />
              <Input label="Phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
              <Input label="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </div>
            {!editing && (
              <div className="form-grid">
                <Input label="Initial password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
                <Input label="Confirm password" type="password" value={form.confirm_password} onChange={(e) => setForm({ ...form, confirm_password: e.target.value })} required />
              </div>
            )}

            <div className="permission-section">
              <h3>Station access</h3>
              <label className="check-line">
                <input type="checkbox" checked={form.all_stations} onChange={(e) => setForm({ ...form, all_stations: e.target.checked })} />
                Grant access to all stations (explicitly authorized)
              </label>
              {!form.all_stations && (
                <div className="check-grid">
                  {stations.map((station) => (
                    <label className="check-line" key={station.id}>
                      <input type="checkbox" checked={form.station_ids.includes(station.id)} onChange={() => toggleStation(station.id)} />
                      {station.code} — {station.name}
                    </label>
                  ))}
                </div>
              )}
            </div>

            <div className="permission-section">
              <h3>Module permissions</h3>
              <p className="muted">No Access by default. Select only the actions this Manager may perform.</p>
              <div className="module-list">
                {modules.map((module) => {
                  const keys = module.actions.map((a) => `${module.code}:${a}`)
                  const checkedCount = keys.filter((k) => form.selected[k]).length
                  return (
                    <div className="module-row" key={module.code}>
                      <button type="button" className="module-head" onClick={() => setOpenModule(openModule === module.code ? null : module.code)}>
                        <span>{module.name}</span>
                        <span className="module-count">{checkedCount ? `${checkedCount}/${keys.length}` : 'No Access'} {openModule === module.code ? '▴' : '▾'}</span>
                      </button>
                      {openModule === module.code && (
                        <div className="action-list">
                          {module.actions.map((action) => (
                            <label className="check-line" key={action}>
                              <input
                                type="checkbox"
                                checked={!!form.selected[`${module.code}:${action}`]}
                                onChange={() => togglePermission(`${module.code}:${action}`)}
                              />
                              {action}
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>

            <div className="modal-actions">
              <Button type="button" variant="secondary" onClick={() => { setCreating(false); setEditing(null) }}>Cancel</Button>
              <Button type="submit">{editing ? 'Save changes' : 'Create Manager'}</Button>
            </div>
          </form>
        </Modal>
      )}

      {resetTarget && (
        <Modal title={`Reset password — ${resetTarget.full_name}`} onClose={() => setResetTarget(null)}>
          <div className="modal-body">
            <Input label="New temporary password" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
            <p className="hint">The Manager will be required to change this password at next login.</p>
            <div className="modal-actions">
              <Button variant="secondary" onClick={() => setResetTarget(null)}>Cancel</Button>
              <Button onClick={submitReset} disabled={newPassword.length < 8}>Reset password</Button>
            </div>
          </div>
        </Modal>
      )}
    </>
  )
}
