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
