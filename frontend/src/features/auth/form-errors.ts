import { ApiError } from '../../shared/api/client'

function firstMessage(value: unknown): string | null {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) {
    for (const item of value) {
      const message = firstMessage(item)
      if (message) return message
    }
  }
  return null
}

export function apiFieldError(error: unknown, field: string): string | null {
  if (
    !(error instanceof ApiError) ||
    typeof error.body !== 'object' ||
    error.body === null
  ) {
    return null
  }
  const fieldEntry = Object.entries(error.body).find(([key]) => key === field)
  return fieldEntry ? firstMessage(fieldEntry[1]) : null
}
