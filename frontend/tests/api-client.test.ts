import { afterEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from '../src/shared/api/client'

afterEach(() => {
  vi.unstubAllGlobals()
  sessionStorage.clear()
  document.cookie = 'csrftoken=; Max-Age=0; path=/'
})

describe('session API client', () => {
  it('sends cookies, CSRF, and active organisation without persisting tokens', async () => {
    document.cookie = 'csrftoken=csrf-secret; path=/'
    sessionStorage.setItem('biashara-pulse.active-organisation', 'org-uuid')
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          csrf_token: 'csrf-secret',
          user: {
            id: 'user-1',
            email: 'owner@example.test',
            first_name: 'Amina',
            last_name: '',
          },
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    await apiClient.login('owner@example.test', 'password')

    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    const headers = new Headers(options.headers)
    expect(options.credentials).toBe('include')
    expect(headers.get('X-CSRFToken')).toBe('csrf-secret')
    expect(headers.get('X-Organisation-ID')).toBe('org-uuid')
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.getItem('biashara-pulse.active-organisation')).toBe(
      'org-uuid',
    )
  })

  it('sends registration and password reset requests to the auth API', async () => {
    document.cookie = 'csrftoken=csrf-secret; path=/'
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Request accepted.' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await apiClient.register('Nia Kamau', 'nia@example.test', 'password-123')
    await apiClient.requestPasswordReset('nia@example.test')
    await apiClient.confirmPasswordReset(
      'uid-1',
      'token-1',
      'new-password-123',
      'new-password-123',
    )

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      '/api/auth/register/',
      '/api/auth/password-reset/request/',
      '/api/auth/password-reset/confirm/uid-1/token-1/',
    ])
    expect(JSON.parse(fetchMock.mock.calls[0][1].body as string)).toEqual({
      full_name: 'Nia Kamau',
      email: 'nia@example.test',
      password: 'password-123',
    })
    expect(JSON.parse(fetchMock.mock.calls[2][1].body as string)).toEqual({
      new_password: 'new-password-123',
      new_password_confirm: 'new-password-123',
    })
  })
})
