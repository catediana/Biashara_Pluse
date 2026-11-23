import { createContext, useContext } from 'react'

import type { AuthUser } from '../../shared/types/api'

export interface AuthContextValue {
  user: AuthUser | null
  isLoading: boolean
  error: Error | null
  signIn: (email: string, password: string) => Promise<AuthUser>
  signOut: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider.')
  }
  return context
}
