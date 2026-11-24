import { useEffect, useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Button, ErrorBanner, Input } from '../components/ui'

export default function Login() {
  const { user, login, loading: authLoading } = useAuth()
  const navigate = useNavigate()
  const [mode, setMode] = useState<'admin' | 'manager'>('admin')
  const [userId, setUserId] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [setupRequired, setSetupRequired] = useState(false)
  const [setupStatusError, setSetupStatusError] = useState('')

  useEffect(() => {
    let active = true
    api.get<{ setup_required: boolean }>('/setup/status')
      .then((data) => {
        if (active) setSetupRequired(data.setup_required)
      })
      .catch((err) => {
        if (active) {
          setSetupStatusError(err instanceof Error ? err.message : 'Unable to check backend setup status.')
        }
      })
    return () => { active = false }
  }, [])

  if (authLoading) return <div className="center-screen">Loading…</div>
  if (user) return <Navigate to="/" replace />

  const handleTabSwitch = (newMode: 'admin' | 'manager') => {
    setMode(newMode)
    setError('')
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      const data = await login(userId.trim(), password)

      // Verify that login matches the chosen portal mode
      const isSuper = data.user.is_super_admin || data.user.role === 'SUPERIOR_ADMIN'
      if (mode === 'admin' && !isSuper) {
        setError("This account is a Station Manager. Please switch to the 'Station Manager' tab to sign in.")
        setBusy(false)
        return
      }
      if (mode === 'manager' && isSuper) {
        setError("This account is a Superior Administrator. Please switch to the 'Admin Login' tab to sign in.")
        setBusy(false)
        return
      }

      navigate(data.user.must_change_password ? '/change-password' : '/', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed. Please verify credentials or ensure backend is running.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-visual">
        <div className="auth-logo">
          <div className="brand-mark large">VE</div>
          <div>
            <h1>VISUAL EYES 360</h1>
            <p>Fuel Station Automation & Control</p>
          </div>
        </div>
        <div className="auth-copy">
          <h2>Control every litre. See every station.</h2>
          <p>Cashless dispensing, independent pulser verification, tank telemetry and multi-station visibility — one secure platform.</p>
        </div>
        <div className="auth-features">
          <span>◉ Live FCC device and tank telemetry</span>
          <span>◉ Verified-payment dispensing (No payment = No fuel)</span>
          <span>◉ Role & station scoped access control (Admin & Manager)</span>
          <span>◉ Independent pulser discrepancy analysis (0.49 L threshold)</span>
        </div>
        <small className="auth-foot">Industrial IoT platform · Phase 6/7 release</small>
      </div>

      <div className="auth-form-side">
        <form className="auth-card" onSubmit={submit}>
          <div className="auth-card-head">
            <h2>Sign in</h2>
            <p>Select your authorized account level to access the platform.</p>
          </div>

          {/* Dual-role Login Tabs */}
          <div className="auth-tabs" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'admin'}
              className={`auth-tab ${mode === 'admin' ? 'active' : ''}`}
              onClick={() => handleTabSwitch('admin')}
            >
              👑 Admin Login
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'manager'}
              className={`auth-tab ${mode === 'manager' ? 'active' : ''}`}
              onClick={() => handleTabSwitch('manager')}
            >
              💼 Manager Login
            </button>
          </div>

          {mode === 'admin' ? (
            <div>
              <span className="role-badge admin">Superior Administrator</span>
              <p className="auth-role-desc">
                Master root authority. Manage all fuel stations, configure 28-module Manager permissions, create Managers, manage fuel prices, and oversee complete platform operations.
              </p>
            </div>
          ) : (
            <div>
              <span className="role-badge manager">Station Manager</span>
              <p className="auth-role-desc">
                Delegated station operator. Access is strictly scoped to your assigned stations and module permissions granted by the Superior Administrator.
              </p>
              <div className="manager-notice-box">
                <strong>Notice:</strong> Only the Superior Administrator can create Manager accounts. Self-registration is disabled. Contact your system owner if you require credentials.
              </div>
            </div>
          )}

          {setupRequired && mode === 'admin' && (
            <div className="notice">
              First installation detected. <Link to="/setup">Create the Superior Administrator account →</Link>
            </div>
          )}

          {setupStatusError && <ErrorBanner message={`Could not check first-run setup: ${setupStatusError}`} />}
          {error && <ErrorBanner message={error} />}

          <Input
            label={mode === 'admin' ? 'Administrator User ID' : 'Manager ID'}
            placeholder={mode === 'admin' ? 'Enter administrator ID' : 'Enter manager ID'}
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            autoComplete="username"
            required
          />

          <div className="password-field">
            <Input
              label="Password"
              type={show ? 'text' : 'password'}
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
            <button type="button" className="toggle-pass" onClick={() => setShow(!show)}>
              {show ? 'Hide' : 'Show'}
            </button>
          </div>

          <div className="auth-row">
            <Link to="/forgot-password">Forgot password?</Link>
          </div>

          <Button type="submit" disabled={busy}>
            {busy ? 'Authenticating…' : mode === 'admin' ? 'Sign in as Superior Administrator' : 'Sign in as Station Manager'}
          </Button>

          <p className="auth-help">
            First installation? Use the one-time setup link above. Otherwise, sign in with the account created for you by your administrator.
          </p>
        </form>
      </div>
    </div>
  )
}
