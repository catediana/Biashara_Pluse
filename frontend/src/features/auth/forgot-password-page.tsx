import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { z } from 'zod'

import { apiClient } from '../../shared/api/client'
import { AuthPageLayout } from './auth-page-layout'

const forgotPasswordSchema = z.object({
  email: z.string().trim().email('Enter a valid email address.'),
})

type ForgotPasswordValues = z.infer<typeof forgotPasswordSchema>

export function ForgotPasswordPage() {
  const [submitted, setSubmitted] = useState(false)
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ForgotPasswordValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: '' },
  })

  const submit = handleSubmit(async ({ email }) => {
    try {
      await apiClient.requestPasswordReset(email)
      setSubmitted(true)
    } catch (error) {
      setError('root', {
        message:
          error instanceof Error
            ? error.message
            : 'Unable to send reset instructions right now.',
      })
    }
  })

  return (
    <AuthPageLayout
      eyebrow="ACCOUNT RECOVERY"
      title="Reset your password"
      description="Enter the email address linked to your account. We’ll send instructions if an account matches."
      footer={
        <Link
          className="font-semibold text-emerald-700 hover:text-emerald-900"
          to="/login"
        >
          ← Back to sign in
        </Link>
      }
    >
      {submitted ? (
        <div className="mt-8">
          <p className="form-success" role="status">
            If an account exists for that email address, password reset
            instructions have been sent.
          </p>
          <p className="mt-4 text-sm leading-6 text-slate-500">
            Check your inbox and follow the secure link to choose a new
            password.
          </p>
          <Link className="button-primary mt-6 w-full justify-center" to="/login">
            Return to sign in
          </Link>
        </div>
      ) : (
        <form className="mt-8 space-y-5" onSubmit={submit} noValidate>
          <div>
            <label className="field-label" htmlFor="reset-email">
              Email address
            </label>
            <input
              autoComplete="email"
              className="field-input"
              id="reset-email"
              type="email"
              placeholder="you@business.com"
              {...register('email')}
            />
            {errors.email && (
              <p className="field-error" role="alert">
                {errors.email.message}
              </p>
            )}
          </div>
          {errors.root && (
            <p className="form-alert" role="alert">
              {errors.root.message}
            </p>
          )}
          <button
            className="button-primary w-full justify-center"
            disabled={isSubmitting}
            type="submit"
          >
            {isSubmitting ? 'Sending instructions…' : 'Send reset link'}
          </button>
        </form>
      )}
    </AuthPageLayout>
  )
}
