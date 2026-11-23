import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { Button, Input } from '../components/ui'

export default function ForgotPassword() {
  const [userId, setUserId] = useState('')
  const [message, setMessage] = useState('')
  const [devToken, setDevToken] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    try {
      const result = await api.post<{ message: string; dev_token?: string }>('/auth/password/forgot', { user_id: userId })
      setMessage(result.message)
      if (result.dev_token) setDevToken(result.dev_token)
    } catch {
      setMessage('If the account exists, a reset link has been issued.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="center-screen">
      <form className="auth-card" onSubmit={submit}>
        <div className="auth-card-head">
          <h2>Reset password</h2>
          <p>Enter your User ID. A reset link will be issued through your registered channel.</p>
        </div>
        {message && <div className="notice">{message}</div>}
        {devToken && (
          <div className="notice code">
            Development token: <code>{devToken}</code><br />
            <Link to={`/reset-password?token=${encodeURIComponent(devToken)}`}>Continue to reset →</Link>
          </div>
        )}
        <Input label="User ID" value={userId} onChange={(e) => setUserId(e.target.value)} required />
        <Button type="submit" disabled={busy}>{busy ? 'Submitting…' : 'Request reset'}</Button>
        <Link to="/login" className="back-link">← Back to sign in</Link>
      </form>
    </div>
  )
}
