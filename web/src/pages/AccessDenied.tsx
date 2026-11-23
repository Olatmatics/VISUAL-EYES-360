import { Link } from 'react-router-dom'
import { Card } from '../components/ui'

export default function AccessDenied() {
  return (
    <Card className="center-card">
      <div className="deny-icon">⛔</div>
      <h2>Access denied</h2>
      <p>Your account does not have permission to view this module, or the requested station is outside your assigned scope.</p>
      <Link to="/">Return to dashboard →</Link>
    </Card>
  )
}
