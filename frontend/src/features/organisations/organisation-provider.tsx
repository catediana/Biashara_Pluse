import { useCallback, useEffect, useState, type ReactNode } from 'react'

import { OrganisationContext } from './organisation-context'
import { useAuth } from '../auth/auth-context'

const STORAGE_KEY = 'biashara-pulse.active-organisation'

function readStoredOrganisation(): string | null {
  try {
    return sessionStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

export function OrganisationProvider({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth()
  const [organisationId, setOrganisationId] = useState<string | null>(
    readStoredOrganisation,
  )

  useEffect(() => {
    if (!isLoading && !user) {
      try {
        sessionStorage.removeItem(STORAGE_KEY)
      } catch {
        // Storage is optional; the signed-out context still hides the selection.
      }
    }
  }, [isLoading, user])

  const selectOrganisation = useCallback((nextId: string | null) => {
    const normalized = nextId?.trim() || null
    setOrganisationId(normalized)
    try {
      if (normalized) {
        sessionStorage.setItem(STORAGE_KEY, normalized)
      } else {
        sessionStorage.removeItem(STORAGE_KEY)
      }
    } catch {
      // The active organisation still works for this page session.
    }
  }, [])

  return (
    <OrganisationContext.Provider
      value={{ organisationId: user ? organisationId : null, selectOrganisation }}
    >
      {children}
    </OrganisationContext.Provider>
  )
}
