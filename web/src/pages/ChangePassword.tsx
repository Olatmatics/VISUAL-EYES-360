import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Button, Card, ErrorBanner, Input, PageHeader } from '../components/ui'

export default function ChangePassword() {
  const { refreshUser } = useAuth()
  const navigate = useNavigate()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    if (next !== confirm) {
      setError('New passwords do not match')
      return
    }
    setBusy(true)
    try {
      await api.post('/auth/password/change', { current_password: current, new_password: next })
      await refreshUser()
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Password change failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader title="Change password" subtitle="You must set a new password before accessing the rest of the system." />
      <Card className="center-card">
        {error && <ErrorBanner message={error} />}
        <form className="auth-card" style={{ border: 0, boxShadow: 'none', padding: 0, margin: '0 auto' }} onSubmit={submit}>
          <Input label="Current password" type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
          <Input label="New password" type="password" value={next} onChange={(e) => setNext(e.target.value)} required />
          <Input label="Confirm new password" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
          <p className="hint">Minimum 8 characters, including upper case, lower case and a number.</p>
          <Button type="submit" disabled={busy}>{busy ? 'Changing…' : 'Change password'}</Button>
        </form>
      </Card>
    </>
  )
}
