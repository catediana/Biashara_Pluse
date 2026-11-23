import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { useAuth } from './auth-context'

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
    <main className="login-page">
      <section className="login-card">
        <Link className="brand-lockup" to="/" aria-label="Biashara Pulse home">
          <span className="brand-mark">B</span>
          <span>
            <strong>Biashara</strong>
            <small>BUSINESS, IN RHYTHM</small>
          </span>
        </Link>
        <div className="mt-12">
          <p className="eyebrow">WELCOME BACK</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">
            Sign in to your workspace
          </h1>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            Keep your day moving with a clear view of your business.
          </p>
        </div>

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
              <span className="text-xs font-medium text-slate-400">
                Secure session
              </span>
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

        <p className="mt-8 text-center text-xs leading-5 text-slate-400">
          Your account is protected with a secure, httpOnly session.
          <br />
          Need help? Contact your workspace administrator.
        </p>
      </section>
      <aside className="login-aside">
        <div className="aside-glow" />
        <div className="aside-content">
          <span className="aside-pill">
            <span className="status-dot" />
            YOUR BUSINESS, IN SYNC
          </span>
          <h2>
            Make every
            <br />
            day <em>count.</em>
          </h2>
          <p>
            One calm, connected workspace for the people, numbers, and
            operations that move your business forward.
          </p>
          <div className="aside-bottom">
            <span>01</span>
            <span className="aside-rule" />
            <span>BUILT FOR HOW YOU DO BUSINESS</span>
          </div>
        </div>
        <div className="aside-orbit orbit-one" />
        <div className="aside-orbit orbit-two" />
      </aside>
    </main>
  )
}
