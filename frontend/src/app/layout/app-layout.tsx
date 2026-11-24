import { useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../../features/auth/auth-context'
import { useOrganisation } from '../../features/organisations/organisation-context'

const navigation = [
  { label: 'Overview', path: '/', mark: '◫' },
  { label: 'Sales & checkout', path: '/sales', mark: '↗' },
  { label: 'Inventory', path: '/inventory', mark: '▤' },
  { label: 'Customers', path: '/customers', mark: '◎' },
  { label: 'Reports', path: '/reports', mark: '⌁' },
  { label: 'Organisations', path: '/organisations', mark: '⌂' },
  { label: 'Staff', path: '/staff', mark: '♙' },
  { label: 'Roles', path: '/roles', mark: '⚿' },
]

const pageTitles: Record<string, string> = {
  '/': 'Overview',
  '/workspace': 'Workspace',
  '/organisations': 'Organisations',
  '/organisations/new': 'Create organisation',
  '/staff': 'Staff management',
  '/roles': 'Roles & permissions',
}

export function AppLayout() {
  const { user, signOut } = useAuth()
  const { organisationId } = useOrganisation()
  const [logoutError, setLogoutError] = useState('')
  const location = useLocation()
  const navigate = useNavigate()
  const title =
    pageTitles[location.pathname] ??
    navigation.find((item) => item.path === location.pathname)?.label ??
    'Workspace'
  const initials = [user?.first_name, user?.last_name]
    .filter(Boolean)
    .map((part) => part?.[0])
    .join('')
    .toUpperCase()

  async function logout() {
    setLogoutError('')
    try {
      await signOut()
      navigate('/login', { replace: true })
    } catch (error) {
      setLogoutError(
        error instanceof Error ? error.message : 'Unable to sign out.',
      )
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink className="brand-lockup sidebar-brand" to="/">
          <span className="brand-mark">B</span>
          <span>
            <strong>Biashara</strong>
            <small>BUSINESS, IN RHYTHM</small>
          </span>
        </NavLink>

        <div className="sidebar-workspace">
          <span className="workspace-avatar">BP</span>
          <span>
            <small>YOUR WORKSPACE</small>
            <strong>{organisationId ? 'Organisation' : 'Not selected'}</strong>
          </span>
          <span className="workspace-caret">⌄</span>
        </div>

        <p className="nav-caption">WORKSPACE</p>
        <nav className="side-nav" aria-label="Main navigation">
          {navigation.map((item) => (
            <NavLink
              className={({ isActive }) => `side-nav-link${isActive ? ' active' : ''}`}
              key={item.label}
              to={item.path}
              end={item.path === '/'}
            >
              <span className="nav-mark" aria-hidden="true">
                {item.mark}
              </span>
              {item.label}
              {item.label === 'Sales & checkout' && (
                <span className="nav-new">POS</span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="help-card">
            <span className="help-spark">✳</span>
            <strong>Here to help</strong>
            <p>Your business tools, all in one place.</p>
          </div>
          <div className="sidebar-footer">
            <span className="avatar">{initials || 'U'}</span>
            <span className="user-summary">
              <strong>{user?.first_name || user?.email}</strong>
              <small>Workspace member</small>
            </span>
            <button
              className="icon-button"
              onClick={logout}
              title="Sign out"
              aria-label="Sign out"
            >
              ↗
            </button>
          </div>
          {logoutError && (
            <p className="sidebar-error" role="alert">
              {logoutError}
            </p>
          )}
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="breadcrumbs">
            <span>Workspace</span>
            <span aria-hidden="true">/</span>
            <strong>{title}</strong>
          </div>
          <div className="topbar-actions">
            <Link className="organisation-switcher" to="/organisations">
              <span className="status-dot" />
              {organisationId ? 'Switch organisation' : 'Select organisation'}
            </Link>
            <span className="topbar-divider" />
            <button className="notification-button" aria-label="Notifications">
              ♧
              <span />
            </button>
            <span className="avatar topbar-avatar">{initials || 'U'}</span>
          </div>
        </header>
        <main className="main-content">
          <Outlet />
        </main>
        <footer className="app-footer">
          <span>© Biashara Pulse</span>
          <span>Built for your business</span>
        </footer>
      </div>
    </div>
  )
}
