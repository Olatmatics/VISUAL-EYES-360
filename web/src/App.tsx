import { useEffect, type ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { GeoProvider } from './geo/GeoContext'
import Layout from './components/Layout'
import { Card } from './components/ui'
import AccessDenied from './pages/AccessDenied'
import AlertsCenter from './pages/AlertsCenter'
import Audit from './pages/Audit'
import ChangePassword from './pages/ChangePassword'
import CustomerWallets from './pages/CustomerWallets'
import Dashboard from './pages/Dashboard'
import Dispensers from './pages/Dispensers'
import FCCDevices from './pages/FCCDevices'
import FleetManagement from './pages/FleetManagement'
import Forecourt from './pages/Forecourt'
import ForgotPassword from './pages/ForgotPassword'
import Login from './pages/Login'
import Payments from './pages/Payments'
import PriceManagement from './pages/PriceManagement'
import PulserReconciliation from './pages/PulserReconciliation'
import Reports from './pages/Reports'
import ResetPassword from './pages/ResetPassword'
import Settings from './pages/Settings'
import Setup from './pages/Setup'
import Stations from './pages/Stations'
import TankReconciliation from './pages/TankReconciliation'
import Tanks from './pages/Tanks'
import Transactions from './pages/Transactions'
import Users from './pages/Users'

function Protected({ children, module, action = 'view' }: { children: ReactNode; module?: string; action?: string }) {
  const { user, loading, can } = useAuth()
  const location = useLocation()
  if (loading) return <div className="center-screen">Loading…</div>
  if (!user) return <Navigate to="/login" replace />
  if (user.must_change_password && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />
  }
  if (module && !can(module, action)) return <Navigate to="/access-denied" replace />
  return <>{children}</>
}

function NotFound() {
  return (
    <Card className="center-card">
      <h2>Page not found</h2>
      <p>The requested module does not exist.</p>
    </Card>
  )
}

export default function App() {
  useEffect(() => {
    const theme = localStorage.getItem('ve_theme')
    if (theme) document.documentElement.dataset.theme = theme
  }, [])

  return (
    <BrowserRouter>
      <AuthProvider>
        <GeoProvider>
          <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/setup" element={<Setup />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route element={<Protected><Layout /></Protected>}>
            <Route path="change-password" element={<Protected><ChangePassword /></Protected>} />
            <Route index element={<Protected module="dashboard"><Dashboard /></Protected>} />
            <Route path="forecourt" element={<Protected module="dispensers"><Forecourt /></Protected>} />
            <Route path="transactions" element={<Protected module="transactions"><Transactions /></Protected>} />
            <Route path="stations" element={<Protected module="stations"><Stations /></Protected>} />
            <Route path="dispensers" element={<Protected module="dispensers"><Dispensers /></Protected>} />
            <Route path="fcc-devices" element={<Protected module="fcc_devices"><FCCDevices /></Protected>} />
            <Route path="tanks" element={<Protected module="tanks"><Tanks /></Protected>} />
            <Route path="pulser-reconciliation" element={<Protected module="pulser"><PulserReconciliation /></Protected>} />
            <Route path="tank-reconciliation" element={<Protected module="tank_reconciliation"><TankReconciliation /></Protected>} />
            <Route path="payments" element={<Protected module="payments"><Payments /></Protected>} />
            <Route path="customers-wallets" element={<Protected module="customers"><CustomerWallets /></Protected>} />
            <Route path="fleets" element={<Protected module="fleet"><FleetManagement /></Protected>} />
            <Route path="prices" element={<Protected module="prices"><PriceManagement /></Protected>} />
            <Route path="alerts" element={<Protected module="alerts"><AlertsCenter /></Protected>} />
            <Route path="reports" element={<Protected module="reports"><Reports /></Protected>} />
            <Route path="users" element={<Protected module="users"><Users /></Protected>} />
            <Route path="audit" element={<Protected module="audit"><Audit /></Protected>} />
            <Route path="settings" element={<Protected module="system_settings"><Settings /></Protected>} />
            <Route path="access-denied" element={<AccessDenied />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
        </GeoProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
