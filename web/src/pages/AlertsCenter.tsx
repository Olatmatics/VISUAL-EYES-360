import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Badge, Button, Card, ErrorBanner, Modal, PageHeader } from '../components/ui'
import type { AlertItem } from '../types'

export default function AlertsCenter() {
  const { can } = useAuth()
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filterSeverity, setFilterSeverity] = useState<string>('')
  const [unresolvedOnly, setUnresolvedOnly] = useState(true)
  const [resolvingAlert, setResolvingAlert] = useState<AlertItem | null>(null)
  const [notes, setNotes] = useState('')

  const load = () => {
    setLoading(true)
    let url = `/alerts?unresolved_only=${unresolvedOnly}`
    if (filterSeverity) url += `&severity=${filterSeverity}`
    api.get<AlertItem[]>(url)
      .then(setAlerts)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load alerts'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [unresolvedOnly, filterSeverity])

  const handleResolve = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!resolvingAlert) return
    try {
      await api.post(`/alerts/${resolvingAlert.id}/resolve`, { notes })
      setResolvingAlert(null)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resolve alert')
    }
  }

  const act = async (id: string, action: string, body: object = {}) => {
    try {
      await api.post(`/alerts/${id}/${action}`, body)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${action} alert`)
    }
  }

  return (
    <>
      <PageHeader
        title="Forecourt Security & Telemetry Alert Center"
        subtitle="Real-time incident response: pulser discrepancies (≥0.49L), tank hatch tampers, water ingress and device alarms"
        action={
          <div style={{ display: 'flex', gap: '8px' }}>
            <Button
              variant={unresolvedOnly ? 'primary' : 'secondary'}
              onClick={() => setUnresolvedOnly(!unresolvedOnly)}
            >
              {unresolvedOnly ? 'Showing Unresolved Alarms' : 'Showing All Alarms'}
            </Button>
            <Button onClick={load} variant="secondary">↻</Button>
          </div>
        }
      />
      {error && <ErrorBanner message={error} />}

      <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
        <Button variant={filterSeverity === '' ? 'primary' : 'secondary'} onClick={() => setFilterSeverity('')}>
          All Severities
        </Button>
        <Button variant={filterSeverity === 'CRITICAL' ? 'danger' : 'secondary'} onClick={() => setFilterSeverity('CRITICAL')}>
          🚨 Critical Only
        </Button>
        <Button variant={filterSeverity === 'WARNING' ? 'secondary' : 'secondary'} onClick={() => setFilterSeverity('WARNING')}>
          ⚠ Warnings Only
        </Button>
      </div>

      <div style={{ display: 'grid', gap: '12px' }}>
        {alerts.map((a) => {
          const isCrit = a.severity === 'CRITICAL'
          return (
            <Card key={a.id} style={{ borderLeft: `6px solid ${isCrit ? 'var(--danger)' : a.severity === 'WARNING' ? 'var(--warning)' : 'var(--primary)'}` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '6px' }}>
                <div>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <Badge tone={isCrit ? 'danger' : a.severity === 'WARNING' ? 'warning' : 'info'}>
                      {a.severity}
                    </Badge>
                    <strong style={{ fontSize: '15px' }}>{a.title}</strong>
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '4px' }}>
                    Station: <strong>{a.station_name}</strong> · Logged: {new Date(a.created_at).toLocaleString()}
                  </div>
                </div>
                <Badge tone={a.is_resolved ? 'success' : 'danger'}>
                  {a.is_resolved ? '✓ RESOLVED' : '● ACTIVE'}
                </Badge>
              </div>

              <p style={{ margin: '8px 0', fontSize: '13px', lineHeight: 1.4 }}>
                {a.description}
              </p>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px' }}>
                <span style={{ fontSize: '11px', color: 'var(--muted)' }}>
                  {a.is_resolved && `Resolved by: ${a.resolved_by} at ${a.resolved_at ? new Date(a.resolved_at).toLocaleTimeString() : ''}`}
                </span>
                {can('alerts', 'manage') && (
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    {!a.acknowledged_at && (
                      <Button variant="secondary" style={{ padding: '4px 10px', fontSize: '12px' }}
                        onClick={() => act(a.id, 'acknowledge')}>Acknowledge</Button>
                    )}
                    <Button variant="secondary" style={{ padding: '4px 10px', fontSize: '12px' }}
                      onClick={() => {
                        const to = window.prompt('Assign to user ID', a.assigned_to || '')
                        if (to) act(a.id, 'assign', { assigned_to: to })
                      }}>Assign</Button>
                    {!a.is_resolved && (
                      <Button variant="secondary" style={{ padding: '4px 10px', fontSize: '12px' }}
                        onClick={() => act(a.id, 'escalate', { notes: 'Escalated from console' })}>Escalate</Button>
                    )}
                    {!a.is_resolved && (
                      <Button variant="secondary" style={{ padding: '4px 10px', fontSize: '12px' }}
                        onClick={() => { setResolvingAlert(a); setNotes('') }}>Investigate & Resolve</Button>
                    )}
                  </div>
                )}
              </div>
            </Card>
          )
        })}
      </div>

      {resolvingAlert && (
        <Modal title={`Resolve Alert — ${resolvingAlert.title}`} onClose={() => setResolvingAlert(null)}>
          <form onSubmit={handleResolve} style={{ display: 'grid', gap: '14px' }}>
            <p style={{ fontSize: '13px', margin: 0 }}>
              {resolvingAlert.description}
            </p>
            <label className="field">
              <span>Resolution Notes & Corrective Actions</span>
              <textarea
                rows={3}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Describe technician verification, physical probe check or reason for closure..."
                required
              />
            </label>
            <Button type="submit">Commit Resolution to Audit Trail</Button>
          </form>
        </Modal>
      )}
    </>
  )
}
