import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { useCallback, type ReactNode } from 'react'

import { ApiError, apiClient } from '../../shared/api/client'
import { AuthContext } from './auth-context'
const CURRENT_USER_KEY = ['auth', 'current-user']

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const queryClient = useQueryClient()
  const currentUser = useQuery({
    queryKey: CURRENT_USER_KEY,
    queryFn: async () => {
      try {
        return (await apiClient.currentUser()).user
      } catch (error) {
        if (
          error instanceof ApiError &&
          (error.status === 401 ||
            (error.status === 403 &&
              typeof error.body === 'object' &&
              error.body !== null &&
              'detail' in error.body &&
              error.body.detail === 'Authentication credentials were not provided.'))
        ) {
          return null
        }
        throw error
      }
    },
  })

  const login = useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      apiClient.login(email, password),
    onSuccess: ({ user }) => {
      queryClient.setQueryData(CURRENT_USER_KEY, user)
    },
  })

  const logout = useMutation({
    mutationFn: apiClient.logout,
    onSuccess: () => {
      queryClient.setQueryData(CURRENT_USER_KEY, null)
      queryClient.clear()
    },
  })

  const signIn = useCallback(
    async (email: string, password: string) =>
      (await login.mutateAsync({ email, password })).user,
    [login],
  )
  const signOut = useCallback(async () => {
    await logout.mutateAsync()
  }, [logout])

  return (
    <AuthContext.Provider
      value={{
        user: currentUser.data ?? null,
        isLoading: currentUser.isPending,
        error: currentUser.error,
        signIn,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
