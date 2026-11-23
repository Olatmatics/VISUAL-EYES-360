import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { Button, ErrorBanner, Input } from '../components/ui'

export default function Setup() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    setup_token: '', full_name: '', user_id: '', password: '', confirm_password: '', phone: '', email: '', recovery_info: '',
  })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [locked, setLocked] = useState(false)

  useEffect(() => {
    api.get<{ setup_required: boolean }>('/setup/status')
      .then((data) => setLocked(!data.setup_required))
      .catch(() => undefined)
  }, [])

  const update = (key: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }))

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      await api.post('/setup/admin', form)
      navigate('/login', { replace: true, state: { notice: 'Administrator created. You can now sign in.' } })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Setup failed')
    } finally {
      setBusy(false)
    }
  }

  if (locked) {
    return (
      <div className="center-screen">
        <div className="auth-card">
          <h2>Setup locked</h2>
          <p>The Superior Administrator account already exists. Initial setup cannot be repeated.</p>
          <Link to="/login">Go to sign in →</Link>
        </div>
      </div>
    )
  }

  return (
    <div className="center-screen setup-screen">
      <form className="auth-card wide" onSubmit={submit}>
        <div className="auth-card-head">
          <div className="brand-mark">VE</div>
          <h2>Initial system setup</h2>
          <p>Create the first Superior Administrator. This can only be done once.</p>
        </div>
        {error && <ErrorBanner message={error} />}
        <div className="form-grid">
          <Input label="One-time setup token" value={form.setup_token} onChange={update('setup_token')} required />
          <Input label="Full name" value={form.full_name} onChange={update('full_name')} required />
          <Input label="Unique User ID" value={form.user_id} onChange={update('user_id')} required />
          <Input label="Phone number" value={form.phone} onChange={update('phone')} required />
          <Input label="Password" type="password" value={form.password} onChange={update('password')} required />
          <Input label="Confirm password" type="password" value={form.confirm_password} onChange={update('confirm_password')} required />
          <Input label="Email (optional)" type="email" value={form.email} onChange={update('email')} />
          <Input label="Recovery information" value={form.recovery_info} onChange={update('recovery_info')} />
        </div>
        <p className="hint">Password must be at least 8 characters with upper, lower and numeric characters.</p>
        <Button type="submit" disabled={busy}>{busy ? 'Creating…' : 'Create Superior Administrator'}</Button>
        <Link to="/login" className="back-link">← Back to sign in</Link>
      </form>
    </div>
  )
}
