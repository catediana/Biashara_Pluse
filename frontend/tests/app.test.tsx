import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AppRoutes } from '../src/app/router'
import { AuthProvider } from '../src/features/auth/auth-provider'
import { OrganisationProvider } from '../src/features/organisations/organisation-provider'
import { ApiError, apiClient } from '../src/shared/api/client'

function renderApp(initialPath = '/') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <OrganisationProvider>
          <MemoryRouter initialEntries={[initialPath]}>
            <AppRoutes />
          </MemoryRouter>
        </OrganisationProvider>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('application shell', () => {
  it('redirects signed-out visitors to the login form', async () => {
    vi.spyOn(apiClient, 'currentUser').mockRejectedValue(
      new ApiError(403, {
        detail: 'Authentication credentials were not provided.',
      }, 'Forbidden'),
    )

    renderApp()

    expect(
      await screen.findByRole('heading', {
        name: 'Sign in to your workspace',
      }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Email address')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
  })

  it('signs in and renders the protected dashboard', async () => {
    const user = userEvent.setup()
    vi.spyOn(apiClient, 'currentUser').mockRejectedValue(
      new ApiError(403, {
        detail: 'Authentication credentials were not provided.',
      }, 'Forbidden'),
    )
    vi.spyOn(apiClient, 'login').mockResolvedValue({
      csrf_token: 'csrf-token',
      user: {
        id: 'user-1',
        email: 'owner@example.test',
        first_name: 'Amina',
        last_name: 'Njeri',
      },
    })

    renderApp('/login')

    await user.type(
      await screen.findByLabelText('Email address'),
      'owner@example.test',
    )
    await user.type(screen.getByLabelText('Password'), 'secret-password')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(
      await screen.findByRole('heading', { name: /good morning, amina/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('navigation', { name: 'Main navigation' }),
    ).toBeInTheDocument()
  })

  it('shows a useful error when login is rejected', async () => {
    const user = userEvent.setup()
    vi.spyOn(apiClient, 'currentUser').mockRejectedValue(
      new ApiError(403, {
        detail: 'Authentication credentials were not provided.',
      }, 'Forbidden'),
    )
    vi.spyOn(apiClient, 'login').mockRejectedValue(
      new Error('Invalid email or password.'),
    )

    renderApp('/login')

    await user.type(
      await screen.findByLabelText('Email address'),
      'owner@example.test',
    )
    await user.type(screen.getByLabelText('Password'), 'wrong-password')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Invalid email or password.',
      )
    })
  })
})
