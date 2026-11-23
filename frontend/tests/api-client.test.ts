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
})
