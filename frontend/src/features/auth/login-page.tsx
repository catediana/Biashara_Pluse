import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { useAuth } from './auth-context'
import { AuthPageLayout } from './auth-page-layout'

const loginSchema = z.object({
  email: z.string().email('Enter a valid email address.'),
  password: z.string().min(1, 'Enter your password.'),
})

type LoginValues = z.infer<typeof loginSchema>

export function LoginPage() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  })

  const submit = handleSubmit(async ({ email, password }) => {
    try {
      await signIn(email, password)
      navigate('/', { replace: true })
    } catch (error) {
      setError('root', {
        message:
          error instanceof Error ? error.message : 'Unable to sign in right now.',
      })
    }
  })

  return (
    <AuthPageLayout
      eyebrow="WELCOME BACK"
      title="Sign in to your workspace"
      description="Keep your day moving with a clear view of your business."
      footer={
        <>
          Your account is protected with a secure, httpOnly session.
          <br />
          Need help? Contact your workspace administrator.
        </>
      }
    >
      <form className="mt-8 space-y-5" onSubmit={submit} noValidate>
        <div>
          <label className="field-label" htmlFor="email">
            Email address
          </label>
          <input
            autoComplete="email"
            className="field-input"
            id="email"
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
        <div>
          <div className="flex items-center justify-between">
            <label className="field-label" htmlFor="password">
              Password
            </label>
            <Link
              className="text-xs font-medium text-emerald-700 hover:text-emerald-900"
              to="/forgot-password"
            >
              Forgot password?
            </Link>
          </div>
          <input
            autoComplete="current-password"
            className="field-input"
            id="password"
            type="password"
            placeholder="Enter your password"
            {...register('password')}
          />
          {errors.password && (
            <p className="field-error" role="alert">
              {errors.password.message}
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
          {isSubmitting ? 'Signing in…' : 'Sign in'}
          {!isSubmitting && <span aria-hidden="true">→</span>}
        </button>
      </form>

      <p className="mt-6 text-center text-xs text-slate-500">
        New to Biashara Pulse?{' '}
        <Link
          className="font-semibold text-emerald-700 hover:text-emerald-900"
          to="/signup"
        >
          Create an account
        </Link>
      </p>
    </AuthPageLayout>
  )
}
