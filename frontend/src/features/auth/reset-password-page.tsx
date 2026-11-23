import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useParams } from 'react-router-dom'
import { z } from 'zod'

import { apiClient } from '../../shared/api/client'
import { AuthPageLayout } from './auth-page-layout'
import { apiFieldError } from './form-errors'

const resetPasswordSchema = z
  .object({
    password: z.string().min(8, 'Use at least 8 characters.'),
    passwordConfirm: z.string().min(1, 'Confirm your password.'),
  })
  .refine((values) => values.password === values.passwordConfirm, {
    path: ['passwordConfirm'],
    message: 'The passwords do not match.',
  })

type ResetPasswordValues = z.infer<typeof resetPasswordSchema>

export function ResetPasswordPage() {
  const { uidb64, token } = useParams<{ uidb64: string; token: string }>()
  const [submitted, setSubmitted] = useState(false)
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { password: '', passwordConfirm: '' },
  })

  const submit = handleSubmit(async ({ password, passwordConfirm }) => {
    if (!uidb64 || !token) {
      setError('root', { message: 'This password reset link is incomplete.' })
      return
    }

    try {
      await apiClient.confirmPasswordReset(
        uidb64,
        token,
        password,
        passwordConfirm,
      )
      setSubmitted(true)
    } catch (error) {
      const passwordMessage = apiFieldError(error, 'new_password')
      const confirmMessage = apiFieldError(error, 'new_password_confirm')
      if (passwordMessage) {
        setError('password', { message: passwordMessage })
      }
      if (confirmMessage) {
        setError('passwordConfirm', { message: confirmMessage })
      }
      if (!passwordMessage && !confirmMessage) {
        setError('root', {
          message:
            error instanceof Error
              ? error.message
              : 'Unable to reset your password. The link may have expired.',
        })
      }
    }
  })

  return (
    <AuthPageLayout
      eyebrow="ACCOUNT RECOVERY"
      title="Choose a new password"
      description="Create a new password to secure your Biashara Pulse account."
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
            Your password has been reset successfully.
          </p>
          <Link className="button-primary mt-6 w-full justify-center" to="/login">
            Continue to sign in
          </Link>
        </div>
      ) : (
        <form className="mt-8 space-y-5" onSubmit={submit} noValidate>
          <div>
            <label className="field-label" htmlFor="new-password">
              New password
            </label>
            <input
              autoComplete="new-password"
              className="field-input"
              id="new-password"
              type="password"
              placeholder="At least 8 characters"
              {...register('password')}
            />
            {errors.password && (
              <p className="field-error" role="alert">
                {errors.password.message}
              </p>
            )}
          </div>
          <div>
            <label className="field-label" htmlFor="new-password-confirm">
              Confirm new password
            </label>
            <input
              autoComplete="new-password"
              className="field-input"
              id="new-password-confirm"
              type="password"
              placeholder="Enter your password again"
              {...register('passwordConfirm')}
            />
            {errors.passwordConfirm && (
              <p className="field-error" role="alert">
                {errors.passwordConfirm.message}
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
            {isSubmitting ? 'Updating password…' : 'Set new password'}
          </button>
        </form>
      )}
    </AuthPageLayout>
  )
}
