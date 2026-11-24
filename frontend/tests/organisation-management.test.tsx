import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AppRoutes } from '../src/app/router'
import { AuthProvider } from '../src/features/auth/auth-provider'
import { OrganisationProvider } from '../src/features/organisations/organisation-provider'
import { apiClient } from '../src/shared/api/client'
import type {
  OrganisationSummary,
  RoleSummary,
  StaffMember,
} from '../src/shared/types/api'

const user = {
  id: 'user-1',
  email: 'owner@example.test',
  first_name: 'Amina',
  last_name: 'Njeri',
}
const organisation: OrganisationSummary = {
  id: 'org-1',
  name: 'Greenview Traders',
  slug: 'greenview-traders',
  sector: 'retail',
  country_code: 'KE',
  currency: 'KES',
  timezone: 'Africa/Nairobi',
  role: 'Owner',
}
const role: RoleSummary = {
  id: '00000000-0000-4000-8000-000000000001',
  name: 'Cashier',
  description: 'Point-of-sale staff',
  is_system: false,
  is_active: true,
  permissions: [],
}

function renderApp(initialPath: string) {
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
  sessionStorage.clear()
  vi.restoreAllMocks()
})

describe('organisation management', () => {
  it('loads the organisation list and selects a workspace', async () => {
    const userEventInstance = userEvent.setup()
    vi.spyOn(apiClient, 'currentUser').mockResolvedValue({ user })
    vi.spyOn(apiClient, 'listOrganisations').mockResolvedValue({
      results: [organisation],
    })

    renderApp('/organisations')

    expect(await screen.findByText('Greenview Traders')).toBeInTheDocument()
    await userEventInstance.click(
      screen.getByRole('button', { name: 'Select workspace' }),
    )

    expect(
      await screen.findByRole('heading', { name: /good morning, amina/i }),
    ).toBeInTheDocument()
    expect(
      sessionStorage.getItem('biashara-pulse.active-organisation'),
    ).toBe('org-1')
  })

  it('creates an organisation, selects it, and opens its workspace', async () => {
    const userEventInstance = userEvent.setup()
    vi.spyOn(apiClient, 'currentUser').mockResolvedValue({ user })
    vi.spyOn(apiClient, 'createOrganisation').mockResolvedValue(organisation)
    vi.spyOn(apiClient, 'listOrganisations').mockResolvedValue({ results: [] })

    renderApp('/organisations/new')

    await userEventInstance.type(
      await screen.findByLabelText('Organisation name'),
      'Greenview Traders',
    )
    await userEventInstance.click(
      screen.getByRole('button', { name: 'Create organisation' }),
    )

    expect(
      await screen.findByRole('heading', { name: /good morning, amina/i }),
    ).toBeInTheDocument()
    expect(apiClient.createOrganisation).toHaveBeenCalledWith(
      {
        name: 'Greenview Traders',
        sector: 'retail',
        country_code: 'KE',
        currency: 'KES',
        timezone: 'Africa/Nairobi',
      },
    )
    expect(
      sessionStorage.getItem('biashara-pulse.active-organisation'),
    ).toBe('org-1')
  })

  it('adds staff to the selected organisation and confirms success', async () => {
    const userEventInstance = userEvent.setup()
    const member: StaffMember = {
      id: 'member-1',
      user: {
        id: 'user-2',
        email: 'cashier@example.test',
        first_name: 'Kendi',
        last_name: 'Wanjiku',
      },
      role: { id: role.id, name: role.name, is_system: false },
      status: 'active',
      all_branches: true,
      branch_ids: [],
      joined_at: null,
    }
    sessionStorage.setItem('biashara-pulse.active-organisation', 'org-1')
    vi.spyOn(apiClient, 'currentUser').mockResolvedValue({ user })
    vi.spyOn(apiClient, 'listRoles').mockResolvedValue({ results: [role] })
    vi.spyOn(apiClient, 'listStaff').mockResolvedValue({ results: [] })
    vi.spyOn(apiClient, 'listBranches').mockResolvedValue({ results: [] })
    vi.spyOn(apiClient, 'createStaffMember').mockResolvedValue(member)

    renderApp('/staff')

    await userEventInstance.type(
      await screen.findByLabelText('Account email'),
      member.user.email,
    )
    await userEventInstance.selectOptions(screen.getByLabelText('Role'), role.id)
    await userEventInstance.click(
      screen.getByRole('button', { name: 'Add staff member' }),
    )

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Staff member added successfully.',
    )
    expect(apiClient.createStaffMember).toHaveBeenCalledWith({
      email: member.user.email,
      role_id: role.id,
      all_branches: true,
      branch_ids: [],
    })
    await waitFor(() => {
      expect(apiClient.listStaff).toHaveBeenCalled()
    })
  })

  it('creates a role with selected permissions', async () => {
    const userEventInstance = userEvent.setup()
    const permissionId = '00000000-0000-4000-8000-000000000002'
    sessionStorage.setItem('biashara-pulse.active-organisation', 'org-1')
    vi.spyOn(apiClient, 'currentUser').mockResolvedValue({ user })
    vi.spyOn(apiClient, 'listRoles').mockResolvedValue({ results: [] })
    vi.spyOn(apiClient, 'listPermissions').mockResolvedValue({
      results: [
        {
          id: permissionId,
          codename: 'retail.products.view',
          name: 'View products',
          module: 'retail',
        },
      ],
    })
    const createRole = vi.spyOn(apiClient, 'createRole').mockResolvedValue(role)

    renderApp('/roles')

    await userEventInstance.type(
      await screen.findByLabelText('Role name'),
      'Cashier',
    )
    await userEventInstance.click(
      screen.getByLabelText(/view products/i),
    )
    await userEventInstance.click(
      screen.getByRole('button', { name: 'Create role' }),
    )

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Role saved successfully.',
    )
    expect(createRole).toHaveBeenCalledWith(
      {
        name: 'Cashier',
        description: '',
        permission_ids: [permissionId],
      },
    )
  })
})
