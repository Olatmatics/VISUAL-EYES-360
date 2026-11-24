import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Badge, Button, Card, ErrorBanner, PageHeader } from '../components/ui'
import type { AlertItem, DashboardSummary, ReportsSummary } from '../types'

export default function Dashboard() {
  const { user, can } = useAuth()
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [report, setReport] = useState<ReportsSummary | null>(null)
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      api.get<DashboardSummary>('/dashboard/summary'),
      api.get<ReportsSummary>('/reports/summary').catch(() => null),
      api.get<AlertItem[]>('/alerts?unresolved_only=true&limit=5').catch(() => []),
    ])
      .then(([s, r, a]) => {
        setSummary(s)
        if (r) setReport(r)
        if (a) setAlerts(a)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load dashboard'))
  }, [])

  const criticalAlerts = alerts.filter((a) => a.severity === 'CRITICAL')

  return (
    <>
      <PageHeader
        title="Industrial Forecourt Operations Dashboard"
        subtitle={`Welcome back, ${user?.full_name}. ${user?.all_stations || user?.is_super_admin ? 'Viewing all authorized stations nationwide.' : 'Viewing your assigned stations.'}`}
        action={
          <div style={{ display: 'flex', gap: '8px' }}>
            <Link to="/forecourt">
              <Button variant="primary">⚡ Live Forecourt Simulator</Button>
            </Link>
          </div>
        }
      />
      {error && <ErrorBanner message={error} />}

      {/* Critical Alert Warning Banner */}
      {criticalAlerts.length > 0 && (
        <div style={{ background: 'rgba(214, 69, 80, 0.12)', border: '1px solid var(--danger)', borderRadius: '12px', padding: '14px 18px', marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <strong style={{ color: 'var(--danger)', fontSize: '15px' }}>
              🚨 {criticalAlerts.length} Active Critical Security / Discrepancy Alert(s)
            </strong>
            <p style={{ margin: '4px 0 0', fontSize: '13px', color: 'var(--text)' }}>
              {criticalAlerts[0].title} — {criticalAlerts[0].description}
            </p>
          </div>
          <Link to="/alerts">
            <Button variant="danger" style={{ whiteSpace: 'nowrap' }}>Inspect & Resolve</Button>
          </Link>
        </div>
      )}

      {/* Primary Forecourt Telemetry Metrics */}
      <div className="metric-grid" style={{ marginBottom: '20px' }}>
        <Link to="/stations" className="metric-link">
          <Card className="metric-card tone-blue">
            <span className="metric-label">Registered Stations</span>
            <strong className="metric-value">{summary?.stations ?? 0}</strong>
            <span className="metric-foot">{summary?.active_stations ?? 0} active nationwide</span>
          </Card>
        </Link>

        <Link to="/dispensers" className="metric-link">
          <Card className="metric-card tone-green">
            <span className="metric-label">Dispensers / Nozzles</span>
            <strong className="metric-value">{summary?.dispensers ?? 0} / {summary?.nozzles ?? 0}</strong>
            <span className="metric-foot">FCC devices assigned by nozzle</span>
          </Card>
        </Link>

        <Link to="/reports" className="metric-link">
          <Card className="metric-card tone-purple">
            <span className="metric-label">Total Forecourt Revenue</span>
            <strong className="metric-value">₦{(report?.financial.total_revenue_ngn ?? 0).toLocaleString()}</strong>
            <span className="metric-foot">OPay Card + Wallet + Transfer</span>
          </Card>
        </Link>

        <Link to="/tanks" className="metric-link">
          <Card className="metric-card tone-amber">
            <span className="metric-label">Physical Storage Stock</span>
            <strong className="metric-value">{(report?.inventory.current_physical_stock_l ?? 0).toLocaleString()} L</strong>
            <span className="metric-foot">{report?.inventory.stock_fill_percentage ?? 0}% of capacity</span>
          </Card>
        </Link>

        <Link to="/pulser-reconciliation" className="metric-link">
          <Card className={`metric-card ${(report?.compliance.discrepancy_incidents ?? 0) > 0 ? 'tone-danger' : 'tone-slate'}`}>
            <span className="metric-label">Pulser Discrepancies</span>
            <strong className="metric-value" style={{ color: (report?.compliance.discrepancy_incidents ?? 0) > 0 ? 'var(--danger)' : undefined }}>
              {report?.compliance.discrepancy_incidents ?? 0}
            </strong>
            <span className="metric-foot">≥0.490 L anomaly threshold</span>
          </Card>
        </Link>

        <Link to="/alerts" className="metric-link">
          <Card className={`metric-card ${alerts.length > 0 ? 'tone-amber' : 'tone-slate'}`}>
            <span className="metric-label">Active Alarms</span>
            <strong className="metric-value">{alerts.length}</strong>
            <span className="metric-foot">Hatch, pulser & water alerts</span>
          </Card>
        </Link>
      </div>

      {/* Quick Access Control Grid */}
      <h3 style={{ margin: '0 0 12px', fontSize: '16px' }}>⚡ Forecourt Control & Operations Center</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '14px', marginBottom: '24px' }}>
        <Card style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <h4 style={{ margin: '0 0 6px', fontSize: '15px' }}>⛽ Live Pump Dispensing</h4>
            <p style={{ fontSize: '12px', color: 'var(--muted)', margin: 0 }}>
              Simulate cash-less card tapping, Wayne dispenser preset control, and real-time dual pulser verification.
            </p>
          </div>
          <Link to="/forecourt" style={{ marginTop: '14px' }}>
            <Button variant="primary" style={{ width: '100%', fontSize: '12px' }}>Open Forecourt Simulator →</Button>
          </Link>
        </Card>

        <Card style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <h4 style={{ margin: '0 0 6px', fontSize: '15px' }}>🛢 Automated Tank Gauges</h4>
            <p style={{ fontSize: '12px', color: 'var(--muted)', margin: 0 }}>
              Inspect live underground storage volume, fuel height, interface water level and ATEX hatch cover sensors.
            </p>
          </div>
          <Link to="/tanks" style={{ marginTop: '14px' }}>
            <Button variant="secondary" style={{ width: '100%', fontSize: '12px' }}>Inspect Tank Levels →</Button>
          </Link>
        </Card>

        <Card style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <h4 style={{ margin: '0 0 6px', fontSize: '15px' }}>🔍 Independent Pulser Audit</h4>
            <p style={{ fontSize: '12px', color: 'var(--muted)', margin: 0 }}>
              Audit dispenser CPU readings against dedicated optical pulser counts. Investigate ≥0.490 L incidents.
            </p>
          </div>
          <Link to="/pulser-reconciliation" style={{ marginTop: '14px' }}>
            <Button variant="secondary" style={{ width: '100%', fontSize: '12px' }}>Pulser Reconciliation →</Button>
          </Link>
        </Card>

        <Card style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <h4 style={{ margin: '0 0 6px', fontSize: '15px' }}>🏷 Remote Fuel Pricing</h4>
            <p style={{ fontSize: '12px', color: 'var(--muted)', margin: 0 }}>
              Dispatch electronic unit prices to Wayne/Gilbarco dispensers per nozzle, station or nationwide.
            </p>
          </div>
          <Link to="/prices" style={{ marginTop: '14px' }}>
            <Button variant="secondary" style={{ width: '100%', fontSize: '12px' }}>Price Management →</Button>
          </Link>
        </Card>
      </div>

      <div className="dashboard-grid">
        <Card>
          <h3>Forecourt Hardware & Network Architecture</h3>
          <div className="status-list">
            <div><span>Forecourt devices</span><strong>FCC device assigned per nozzle</strong></div>
            <div><span>Tank telemetry</span><strong>Tank controller (Modbus RTU)</strong></div>
            <div><span>Network Standard</span><Badge tone="success">Wi-Fi 6 + 4G LTE SIM Only (Zero Ethernet)</Badge></div>
            <div><span>Payment Rule</span><Badge tone="info">No Verified Payment, No Dispensing</Badge></div>
            <div><span>Discrepancy Threshold</span><strong>0.490 Litres</strong></div>
          </div>
        </Card>

        <Card>
          <h3>Active Deployment Scope</h3>
          <div className="status-list">
            <div><span>Operator Role</span><Badge tone="info">{user?.role?.replace('_', ' ')}</Badge></div>
            <div><span>Station Access</span><strong>{user?.all_stations || user?.is_super_admin ? 'All Stations Nationwide' : `${user?.stations?.length ?? 0} Assigned Stations`}</strong></div>
            <div><span>Audit Logging</span><Badge tone="success">Continuous SHA-256 Ledger</Badge></div>
            <div><span>Database Layer</span><strong>Supabase / PostgreSQL Schema Active</strong></div>
          </div>
        </Card>
      </div>
    </>
  )
}
