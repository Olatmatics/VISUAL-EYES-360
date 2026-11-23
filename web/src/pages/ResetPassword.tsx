import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { Button, ErrorBanner, Input } from '../components/ui'

export default function ResetPassword() {
  const [params] = useSearchParams()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (password !== confirm) {
      setError('Passwords do not match')
      return
    }
    setError('')
    setBusy(true)
    try {
      await api.post('/auth/password/reset', { token: params.get('token'), new_password: password })
      setDone(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reset failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="center-screen">
      <form className="auth-card" onSubmit={submit}>
        <div className="auth-card-head">
          <h2>Choose a new password</h2>
          <p>Use at least 8 characters with upper, lower and numeric characters.</p>
        </div>
        {error && <ErrorBanner message={error} />}
        {done ? (
          <div className="notice">Password reset complete. <Link to="/login">Sign in →</Link></div>
        ) : (
          <>
            <Input label="New password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            <Input label="Confirm password" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
            <Button type="submit" disabled={busy}>{busy ? 'Saving…' : 'Reset password'}</Button>
          </>
        )}
      </form>
    </div>
  )
}
