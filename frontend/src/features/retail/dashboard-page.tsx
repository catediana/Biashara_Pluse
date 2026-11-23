import { Link } from 'react-router-dom'

import { useAuth } from '../auth/auth-context'
import { useOrganisation } from '../organisations/organisation-context'

const shortcuts = [
  { title: 'Retail operations', text: 'Products, checkout, shifts and stock' },
  { title: 'Business reports', text: 'Sales, inventory, debt and profit' },
  { title: 'Team & access', text: 'People, roles and branch permissions' },
]

export function DashboardPage() {
  const { user } = useAuth()
  const { organisationId } = useOrganisation()
  const name = user?.first_name || user?.email.split('@')[0] || 'there'

  return (
    <div className="page-content">
      <div className="welcome-row">
        <div>
          <p className="eyebrow">YOUR BUSINESS IS READY</p>
          <h1 className="page-title">
            Good morning, {name}
            <span aria-hidden="true"> ✳</span>
          </h1>
          <p className="page-description">
            Here’s your workspace. Let’s make today a good one.
          </p>
        </div>
        <div className="date-chip">
          <span className="date-icon">◷</span>
          DAILY SNAPSHOT
        </div>
      </div>

      {!organisationId ? (
        <section className="organisation-notice">
          <div className="notice-icon">⌂</div>
          <div>
            <h2>Select your organisation</h2>
            <p>
              Enter an organisation ID in the top bar to load its workspace.
              Your administrator can provide this ID.
            </p>
          </div>
        </section>
      ) : (
        <section className="active-organisation">
          <span className="status-dot" />
          <span>Workspace selected</span>
          <code>{organisationId}</code>
        </section>
      )}

      <section className="section-heading">
        <div>
          <p className="eyebrow">YOUR WORKSPACE</p>
          <h2>Start with what matters</h2>
        </div>
        <span className="section-hint">Everything in one place</span>
      </section>

      <div className="shortcut-grid">
        {shortcuts.map((shortcut, index) => (
          <Link className="shortcut-card" key={shortcut.title} to="/workspace">
            <span className={`shortcut-index shortcut-index-${index + 1}`}>
              0{index + 1}
            </span>
            <span className="shortcut-arrow" aria-hidden="true">
              ↗
            </span>
            <h3>{shortcut.title}</h3>
            <p>{shortcut.text}</p>
          </Link>
        ))}
      </div>

      <section className="getting-started">
        <div className="getting-icon">✦</div>
        <div>
          <p className="eyebrow">A GOOD PLACE TO BEGIN</p>
          <h2>Your business, at a glance.</h2>
          <p>
            Choose an organisation to connect your team and start seeing
            meaningful activity here.
          </p>
        </div>
        <span className="getting-decoration" aria-hidden="true">
          BP
        </span>
      </section>
    </div>
  )
}

export function WorkspacePlaceholder() {
  return (
    <div className="page-content">
      <p className="eyebrow">WORKSPACE</p>
      <h1 className="page-title">Coming into focus</h1>
      <p className="page-description">
        This area will be available as your workspace features are connected.
      </p>
    </div>
  )
}
