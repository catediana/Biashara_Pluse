import { createContext, useContext } from 'react'

export interface OrganisationContextValue {
  organisationId: string | null
  selectOrganisation: (organisationId: string | null) => void
}

export const OrganisationContext =
  createContext<OrganisationContextValue | null>(null)

export function useOrganisation() {
  const context = useContext(OrganisationContext)
  if (!context) {
    throw new Error(
      'useOrganisation must be used within OrganisationProvider.',
    )
  }
  return context
}
