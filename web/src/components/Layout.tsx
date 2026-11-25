import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import DeviceTicker from './DeviceTicker'

type NavItem = { to: string; label: string; module: string; action: string; icon: string; section?: string }

const NAV: NavItem[] = [
  { to: '/quick-setup', label: 'Start Here · Set Up', module: 'dashboard', action: 'view', icon: '⚡', section: 'START HERE' },
  // Operations
  { to: '/', label: 'Operations Dashboard', module: 'dashboard', action: 'view', icon: '▦', section: 'OPERATIONS' },
  { to: '/forecourt', label: 'Forecourt & Dispense', module: 'dispensers', action: 'view', icon: '⚡' },
  { to: '/transactions', label: 'Fuel Transactions', module: 'transactions', action: 'view', icon: '📑' },

  // Forecourt Infrastructure
  { to: '/locations', label: 'Browse by Location', module: 'stations', action: 'view', icon: '🗺', section: 'INFRASTRUCTURE' },
  { to: '/stations', label: 'Stations Network', module: 'stations', action: 'view', icon: '◈' },
  { to: '/dispensers', label: 'Dispensers & Nozzles', module: 'dispensers', action: 'view', icon: '⛽' },
  { to: '/fcc-devices', label: 'Devices', module: 'fcc_devices', action: 'view', icon: '📡' },
  { to: '/tanks', label: 'ATG Storage Tanks', module: 'tanks', action: 'view', icon: '🛢' },

  // Audits & Discrepancies
  { to: '/pulser-reconciliation', label: 'Pulser Verification (0.49L)', module: 'pulser', action: 'view', icon: '🔍', section: 'RECONCILIATION' },
  { to: '/tank-reconciliation', label: 'Tank Inventory Recon', module: 'tank_reconciliation', action: 'view', icon: '📊' },

  // Cashless & Accounts
  { to: '/payments', label: 'OPay POS & Cashless', module: 'payments', action: 'view', icon: '💳', section: 'PAYMENTS & FLEET' },
  { to: '/customers-wallets', label: 'RFID Special Wallets', module: 'customers', action: 'view', icon: '👛' },
  { to: '/fleets', label: 'Fleet Management', module: 'fleet', action: 'view', icon: '🚛' },

  // Governance & Security
  { to: '/prices', label: 'Fuel Price Management', module: 'prices', action: 'view', icon: '🏷', section: 'MANAGEMENT' },
  { to: '/alerts', label: 'Alerts & Security Center', module: 'alerts', action: 'view', icon: '🚨' },
  { to: '/reports', label: 'Executive Reports', module: 'reports', action: 'view', icon: '📈' },
  { to: '/users', label: 'User Management', module: 'users', action: 'view', icon: '♙' },
  { to: '/audit', label: 'Audit Log Trail', module: 'audit', action: 'view', icon: '≡' },
  { to: '/settings', label: 'Platform & APN Settings', module: 'system_settings', action: 'view', icon: '⚙' },
]

export default function Layout() {
  const { user, logout, can } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [dark, setDark] = useState(() => localStorage.getItem('ve_theme') === 'dark')

  const toggleTheme = () => {
    const next = !dark
    setDark(next)
    localStorage.setItem('ve_theme', next ? 'dark' : 'light')
    document.documentElement.dataset.theme = next ? 'dark' : 'light'
  }

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  const links = NAV.filter((item) => can(item.module, item.action))

  return (
    <div className="app-shell">
      {open && <div className="sidebar-overlay" onClick={() => setOpen(false)} />}
      <aside className={`sidebar ${open ? 'open' : ''}`} style={{ overflowY: 'auto' }}>
        <div className="brand">
          <div className="brand-mark">VE</div>
          <div>
            <strong>VISUAL EYES 360</strong>
            <small>Fuel Station Automation</small>
          </div>
        </div>
        <nav style={{ paddingBottom: '30px' }}>
          {links.map((item, idx) => (
            <div key={item.to}>
              {item.section && (
                <span className="nav-label" style={{ marginTop: idx > 0 ? '16px' : '8px', display: 'block', fontSize: '10px', letterSpacing: '0.05em' }}>
                  {item.section}
                </span>
              )}
              <NavLink
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                onClick={() => setOpen(false)}
              >
                <span className="nav-icon">{item.icon}</span>
                {item.label}
              </NavLink>
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="avatar">{user?.full_name?.slice(0, 2).toUpperCase()}</div>
          <div className="user-meta">
            <strong>{user?.full_name}</strong>
            <small>{user?.user_id} · {user?.role?.replace('_', ' ')}</small>
          </div>
          <button className="icon-btn" onClick={handleLogout} title="Logout" aria-label="Logout">⏻</button>
        </div>
      </aside>

      <div className="main-area">
        <header className="topbar">
          <button className="menu-btn" onClick={() => setOpen(!open)} aria-label="Menu">☰</button>
          <div className="topbar-title">VISUAL EYES 360 · Forecourt Automation & Control System</div>
          <div className="topbar-actions">
            <span className={`status-dot ${user?.role === 'SUPERIOR_ADMIN' ? 'admin' : ''}`} />
            <button className="icon-btn" onClick={toggleTheme} title="Toggle theme" aria-label="Toggle theme">
              {dark ? '☀' : '☾'}
            </button>
          </div>
        </header>
        <DeviceTicker />
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
