import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'

import { useOrganisation } from './organisation-context'
import { apiClient } from '../../shared/api/client'

const ORGANISATIONS_KEY = ['organisations']

export function OrganisationsPage() {
  const { organisationId, selectOrganisation } = useOrganisation()
  const navigate = useNavigate()
  const organisations = useQuery({
    queryKey: ORGANISATIONS_KEY,
    queryFn: apiClient.listOrganisations,
  })

  return (
    <div className="page-content">
      <div className="welcome-row">
        <div>
          <p className="eyebrow">YOUR WORKSPACES</p>
          <h1 className="page-title">Organisations</h1>
          <p className="page-description">
            Choose the business workspace you want to work in.
          </p>
        </div>
        <Link className="button-primary" to="/organisations/new">
          Create organisation <span aria-hidden="true">+</span>
        </Link>
      </div>

      {organisations.isPending ? (
        <p className="state-card mt-8" role="status">
          Loading your organisations…
        </p>
      ) : organisations.isError ? (
        <section className="state-card state-error mt-8" role="alert">
          <h2>Organisations could not be loaded</h2>
          <p>{organisations.error.message}</p>
          <button
            className="button-primary mt-4"
            onClick={() => void organisations.refetch()}
          >
            Try again
          </button>
        </section>
      ) : organisations.data.results.length === 0 ? (
        <section className="state-card mt-8">
          <span className="notice-icon" aria-hidden="true">
            ⌂
          </span>
          <h2 className="mt-4 text-base font-semibold text-slate-800">
            No organisations yet
          </h2>
          <p className="mt-2 text-sm text-slate-500">
            Create an organisation to set up your business workspace.
          </p>
          <Link className="button-primary mt-5" to="/organisations/new">
            Create your first organisation
          </Link>
        </section>
      ) : (
        <div className="organisation-grid mt-8">
          {organisations.data.results.map((organisation) => {
            const active = organisation.id === organisationId
            return (
              <article
                className={`organisation-card${active ? ' organisation-card-active' : ''}`}
                key={organisation.id}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="eyebrow">{organisation.sector}</p>
                    <h2 className="mt-2 text-lg font-semibold text-slate-900">
                      {organisation.name}
                    </h2>
                  </div>
                  {active && <span className="selected-badge">SELECTED</span>}
                </div>
                <p className="mt-3 text-xs text-slate-500">
                  {organisation.country_code} · {organisation.currency} ·{' '}
                  {organisation.timezone}
                </p>
                <p className="mt-2 text-xs text-slate-500">
                  Your role: <strong>{organisation.role ?? 'Member'}</strong>
                </p>
                <button
                  className={active ? 'button-secondary mt-6' : 'button-primary mt-6'}
                  disabled={active}
                  onClick={() => {
                    selectOrganisation(organisation.id)
                    navigate('/')
                  }}
                  type="button"
                >
                  {active ? 'Current workspace' : 'Select workspace'}
                </button>
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}
