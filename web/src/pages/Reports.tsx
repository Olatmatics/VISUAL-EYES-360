import { useEffect, useState } from 'react'
import { api, downloadFile } from '../api/client'
import { Button, Card, ErrorBanner, PageHeader } from '../components/ui'
import type { ReportsSummary } from '../types'

export default function Reports() {
  const [data, setData] = useState<ReportsSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [datasets, setDatasets] = useState<{ name: string; module: string }[]>([])

  const load = () => {
    setLoading(true)
    api.get<ReportsSummary>('/reports/summary')
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to generate report'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
    api.get<{ name: string; module: string }[]>('/reports/export/datasets')
      .then(setDatasets)
      .catch(() => setDatasets([]))
  }, [])

  const exportDataset = (name: string, fmt: 'csv' | 'xlsx') =>
    downloadFile(`/reports/export/${name}?fmt=${fmt}`, `ve360-${name}.${fmt}`)
      .catch((err) => setError(err instanceof Error ? err.message : 'Export failed'))

  const exportCSV = () => {
    if (!data) return
    const rows = [
      ['Metric Category', 'Key', 'Value', 'Unit'],
      ['Financial', 'Total Revenue', data.financial.total_revenue_ngn, 'NGN'],
      ['Financial', 'OPay POS Card', data.financial.opay_pos_ngn, 'NGN'],
      ['Financial', 'RFID Wallets', data.financial.rfid_wallet_ngn, 'NGN'],
      ['Financial', 'Bank Transfers', data.financial.bank_transfer_ngn, 'NGN'],
      ['Volumetric', 'Total CPU Dispensed', data.volumetric.total_dispensed_cpu_l, 'Litres'],
      ['Volumetric', 'Total Pulser Verified', data.volumetric.total_verified_pulser_l, 'Litres'],
      ['Volumetric', 'Measurement Delta', data.volumetric.measurement_difference_l, 'Litres'],
      ['Volumetric', 'PMS Total', data.volumetric.pms_volume_l, 'Litres'],
      ['Volumetric', 'AGO Total', data.volumetric.ago_volume_l, 'Litres'],
      ['Inventory', 'Total Storage Capacity', data.inventory.total_storage_capacity_l, 'Litres'],
      ['Inventory', 'Current Stock Level', data.inventory.current_physical_stock_l, 'Litres'],
      ['Compliance', 'Total Transactions', data.compliance.total_transactions, 'Count'],
      ['Compliance', 'Discrepancy Incidents (>=0.49L)', data.compliance.discrepancy_incidents, 'Count'],
      ['Compliance', 'Compliance Rate', data.compliance.compliance_rate_percent, 'Percent'],
    ]
    const csvContent = 'data:text/csv;charset=utf-8,' + rows.map((e) => e.join(',')).join('\n')
    const encodedUri = encodeURI(csvContent)
    const link = document.createElement('a')
    link.setAttribute('href', encodedUri)
    link.setAttribute('download', `visual_eyes_360_report_${new Date().toISOString().slice(0, 10)}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  return (
    <>
      <PageHeader
        title="Forecourt Operations & Compliance Reports"
        subtitle="Financial revenue auditing, dual-measurement pulser reconciliation and tank throughput"
        action={
          <div style={{ display: 'flex', gap: '8px' }}>
            <Button onClick={exportCSV} variant="primary">📥 Export CSV Report</Button>
            <Button onClick={load} variant="secondary">↻</Button>
          </div>
        }
      />
      {error && <ErrorBanner message={error} />}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px', marginBottom: '20px' }}>
        {/* Financial Revenue Summary */}
        <Card>
          <h3 style={{ marginBottom: '12px' }}>💰 Revenue by Payment Channel</h3>
          <div style={{ display: 'grid', gap: '8px', fontSize: '13px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Total Gross Forecourt Sales:</span>
              <strong style={{ fontSize: '16px', color: 'var(--primary)' }}>₦{data?.financial.total_revenue_ngn.toLocaleString() ?? 0}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--muted)' }}>
              <span>OPay SmartPOS Terminals:</span>
              <span>₦{data?.financial.opay_pos_ngn.toLocaleString() ?? 0}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--muted)' }}>
              <span>Special Customer RFID Wallets:</span>
              <span>₦{data?.financial.rfid_wallet_ngn.toLocaleString() ?? 0}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--muted)' }}>
              <span>Direct Bank Transfers:</span>
              <span>₦{data?.financial.bank_transfer_ngn.toLocaleString() ?? 0}</span>
            </div>
          </div>
        </Card>

        {/* Volumetric Dispensing */}
        <Card>
          <h3 style={{ marginBottom: '12px' }}>⛽ Volumetric Sales & Verification</h3>
          <div style={{ display: 'grid', gap: '8px', fontSize: '13px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Total Volume (Dispenser CPU):</span>
              <strong>{data?.volumetric.total_dispensed_cpu_l.toLocaleString() ?? 0} L</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Verified Volume (Optical Pulser):</span>
              <strong style={{ color: 'var(--success)' }}>{data?.volumetric.total_verified_pulser_l.toLocaleString() ?? 0} L</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid var(--border)', paddingTop: '4px' }}>
              <span>Measurement Delta:</span>
              <span>{data?.volumetric.measurement_difference_l ?? 0} L</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--muted)', fontSize: '12px' }}>
              <span>PMS: {data?.volumetric.pms_volume_l.toLocaleString()} L · AGO: {data?.volumetric.ago_volume_l.toLocaleString()} L</span>
            </div>
          </div>
        </Card>

        {/* Tank Throughput */}
        <Card>
          <h3 style={{ marginBottom: '12px' }}>🛢 Underground Storage Inventory</h3>
          <div style={{ display: 'grid', gap: '8px', fontSize: '13px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Total Forecourt Storage Capacity:</span>
              <strong>{data?.inventory.total_storage_capacity_l.toLocaleString() ?? 0} L</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Physical Closing Stock:</span>
              <strong>{data?.inventory.current_physical_stock_l.toLocaleString() ?? 0} L ({data?.inventory.stock_fill_percentage}%)</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--muted)' }}>
              <span>Available Ullage (Ullage Space):</span>
              <span>{data?.inventory.ullage_available_l.toLocaleString() ?? 0} L</span>
            </div>
          </div>
        </Card>

        {/* Forecourt Compliance */}
        <Card>
          <h3 style={{ marginBottom: '12px' }}>🛡 Compliance & Anomaly Metrics</h3>
          <div style={{ display: 'grid', gap: '8px', fontSize: '13px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Total Monitored Transactions:</span>
              <strong>{data?.compliance.total_transactions ?? 0}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Discrepancy Alerts (≥0.490 L):</span>
              <strong style={{ color: data && data.compliance.discrepancy_incidents > 0 ? 'var(--danger)' : 'var(--text)' }}>
                {data?.compliance.discrepancy_incidents ?? 0}
              </strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Overall Measurement Compliance:</span>
              <strong style={{ color: 'var(--success)', fontSize: '15px' }}>{data?.compliance.compliance_rate_percent ?? 100}%</strong>
            </div>
          </div>
        </Card>
      </div>

      <Card>
        <h3 style={{ marginBottom: '4px' }}>📤 Operational Data Exports</h3>
        <p className="muted" style={{ fontSize: '13px', marginTop: 0 }}>
          Live records exported from the database with your station and geographic access applied.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '10px' }}>
          {datasets.map((dataset) => (
            <div key={dataset.name} className="export-row">
              <span style={{ fontSize: '13px', textTransform: 'capitalize' }}>{dataset.name.replace(/-/g, ' ')}</span>
              <div style={{ display: 'flex', gap: '6px' }}>
                <Button variant="secondary" style={{ padding: '4px 10px', fontSize: '12px' }}
                  onClick={() => exportDataset(dataset.name, 'csv')}>CSV</Button>
                <Button variant="secondary" style={{ padding: '4px 10px', fontSize: '12px' }}
                  onClick={() => exportDataset(dataset.name, 'xlsx')}>Excel</Button>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </>
  )
}
