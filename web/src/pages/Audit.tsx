import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { Card, EmptyState, ErrorBanner, PageHeader } from '../components/ui'

interface AuditEntry {
  id: string
  actor: string | null
  action: string
  entity_type: string | null
  entity_id: string | null
  before: string | null
  after: string | null
  ip: string | null
  created_at: string
}

export default function Audit() {
  const [rows, setRows] = useState<AuditEntry[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    api.get<AuditEntry[]>('/audit-logs?limit=200')
      .then(setRows)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load audit log'))
  }, [])

  return (
    <>
      <PageHeader title="Audit Log" subtitle="Tamper-evident record of administrative and account actions." />
      {error && <ErrorBanner message={error} />}
      <Card>
        {rows.length === 0 ? (
          <EmptyState title="No activity" message="Actions will appear here as they occur." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Entity</th><th>IP</th></tr></thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>{new Date(row.created_at).toLocaleString()}</td>
                    <td>{row.actor || 'System'}</td>
                    <td><strong>{row.action.replaceAll('_', ' ')}</strong></td>
                    <td>{row.entity_type ? `${row.entity_type}: ${row.entity_id?.slice(0, 8)}` : '—'}</td>
                    <td>{row.ip || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
