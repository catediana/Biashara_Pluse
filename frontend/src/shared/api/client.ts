import type {
  AuthResponse,
  BranchListResponse,
  CurrentUserResponse,
  MessageResponse,
  OrganisationCreateInput,
  OrganisationListResponse,
  OrganisationSummary,
  PermissionListResponse,
  RoleListResponse,
  RoleSummary,
  StaffListResponse,
  StaffMember,
} from '../types/api'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(
  /\/$/,
  '',
)

export class ApiError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(status: number, body: unknown, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

function csrfCookie(): string | null {
  const cookie = document.cookie
    .split('; ')
    .find((entry) => entry.startsWith('csrftoken='))
  return cookie ? decodeURIComponent(cookie.slice('csrftoken='.length)) : null
}

async function ensureCsrfToken(): Promise<string> {
  const existing = csrfCookie()
  if (existing) return existing

  const response = await fetch(`${API_BASE_URL}/auth/csrf/`, {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    throw new ApiError(
      response.status,
      await response.json().catch(() => null),
      'Could not initialize a secure session.',
    )
  }

  const body: { csrf_token?: string } = await response.json()
  const token = csrfCookie() ?? body.csrf_token
  if (!token) {
    throw new Error('The server did not provide a CSRF token.')
  }
  return token
}

function errorMessage(body: unknown, fallback: string): string {
  if (
    typeof body === 'object' &&
    body !== null &&
    'detail' in body &&
    typeof body.detail === 'string'
  ) {
    return body.detail
  }
  if (typeof body === 'object' && body !== null) {
    const messages = Object.values(body)
      .flatMap((value) => (Array.isArray(value) ? value : [value]))
      .filter((value): value is string => typeof value === 'string')
    if (messages.length) return messages.join(' ')
  }
  return fallback
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase()
  const headers = new Headers(options.headers)
  headers.set('Accept', 'application/json')
  if (options.body && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  if (!['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method)) {
    headers.set('X-CSRFToken', await ensureCsrfToken())
  }
  try {
    const organisationId = sessionStorage.getItem(
      'biashara-pulse.active-organisation',
    )
    if (organisationId) headers.set('X-Organisation-ID', organisationId)
  } catch {
    // Organisation selection remains optional when storage is unavailable.
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    method,
    headers,
    credentials: 'include',
  })

  if (response.status === 204) return undefined as T

  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    throw new ApiError(
      response.status,
      body,
      errorMessage(body, `Request failed with status ${response.status}.`),
    )
  }
  return body as T
}

export const apiClient = {
  currentUser: () => request<CurrentUserResponse>('/auth/me/'),
  login: (email: string, password: string) =>
    request<AuthResponse>('/auth/login/', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  register: (fullName: string, email: string, password: string) =>
    request<AuthResponse>('/auth/register/', {
      method: 'POST',
      body: JSON.stringify({
        full_name: fullName,
        email,
        password,
      }),
    }),
  requestPasswordReset: (email: string) =>
    request<MessageResponse>('/auth/password-reset/request/', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),
  confirmPasswordReset: (
    uidb64: string,
    token: string,
    newPassword: string,
    newPasswordConfirm: string,
  ) =>
    request<MessageResponse>(
      `/auth/password-reset/confirm/${encodeURIComponent(uidb64)}/${encodeURIComponent(token)}/`,
      {
        method: 'POST',
        body: JSON.stringify({
          new_password: newPassword,
          new_password_confirm: newPasswordConfirm,
        }),
      },
    ),
  logout: () => request<void>('/auth/logout/', { method: 'POST' }),
  sessionRefresh: () =>
    request<AuthResponse>('/auth/session/refresh/', { method: 'POST' }),
  listOrganisations: () =>
    request<OrganisationListResponse>('/organisations/'),
  createOrganisation: (data: OrganisationCreateInput) =>
    request<OrganisationSummary>('/organisations/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  listStaff: () => request<StaffListResponse>('/organisations/members/'),
  listBranches: () => request<BranchListResponse>('/organisations/branches/'),
  createStaffMember: (data: {
    email: string
    role_id: string
    all_branches: boolean
    branch_ids: string[]
  }) =>
    request<StaffMember>('/organisations/members/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateStaffMember: (
    membershipId: string,
    data: {
      role_id?: string
      status?: StaffMember['status']
      all_branches?: boolean
      branch_ids?: string[]
    },
  ) =>
    request<StaffMember>(`/organisations/members/${membershipId}/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  listRoles: () => request<RoleListResponse>('/rbac/roles/'),
  createRole: (data: {
    name: string
    description: string
    permission_ids: string[]
  }) =>
    request<RoleSummary>('/rbac/roles/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateRole: (
    roleId: string,
    data: {
      name?: string
      description?: string
      is_active?: boolean
      permission_ids?: string[]
    },
  ) =>
    request<RoleSummary>(`/rbac/roles/${roleId}/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  listPermissions: () => request<PermissionListResponse>('/rbac/permissions/'),
}
