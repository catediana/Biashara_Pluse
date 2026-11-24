export interface AuthUser {
  id: string
  email: string
  first_name: string
  last_name: string
}

export interface AuthResponse {
  user: AuthUser
  csrf_token: string
}

export interface CurrentUserResponse {
  user: AuthUser
}

export interface MessageResponse {
  detail: string
}

export interface OrganisationSummary {
  id: string
  name: string
  slug: string
  sector: string
  country_code: string
  currency: string
  timezone: string
  role?: string
}

export interface OrganisationListResponse {
  results: OrganisationSummary[]
}

export interface OrganisationCreateInput {
  name: string
  sector: string
  country_code: string
  currency: string
  timezone: string
}

export interface StaffMember {
  id: string
  user: {
    id: string
    email: string
    first_name: string
    last_name: string
  }
  role: { id: string; name: string; is_system: boolean }
  status: 'active' | 'invited' | 'suspended'
  all_branches: boolean
  branch_ids: string[]
  joined_at: string | null
}

export interface StaffListResponse {
  results: StaffMember[]
}

export interface BranchSummary {
  id: string
  name: string
  code: string
}

export interface BranchListResponse {
  results: BranchSummary[]
}

export interface PermissionSummary {
  id: string
  codename: string
  name: string
  module: string
}

export interface PermissionListResponse {
  results: PermissionSummary[]
}

export interface RoleSummary {
  id: string
  name: string
  description: string
  is_system: boolean
  is_active: boolean
  permissions: PermissionSummary[]
}

export interface RoleListResponse {
  results: RoleSummary[]
}
