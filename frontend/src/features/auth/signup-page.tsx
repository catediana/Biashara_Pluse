import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { useAuth } from './auth-context'
import { AuthPageLayout } from './auth-page-layout'
import { apiFieldError } from './form-errors'

const signupSchema = z
  .object({
    fullName: z.string().trim().min(1, 'Enter your full name.').max(150),
    email: z.string().trim().email('Enter a valid email address.'),
    password: z.string().min(8, 'Use at least 8 characters.'),
    passwordConfirm: z.string().min(1, 'Confirm your password.'),
  })
  .refine((values) => values.password === values.passwordConfirm, {
    path: ['passwordConfirm'],
    message: 'The passwords do not match.',
  })

type SignupValues = z.infer<typeof signupSchema>

export function SignupPage() {
  const { signUp } = useAuth()
  const navigate = useNavigate()
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<SignupValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: {
      fullName: '',
      email: '',
      password: '',
      passwordConfirm: '',
    },
  })

  const submit = handleSubmit(async ({ fullName, email, password }) => {
    try {
      await signUp(fullName, email, password)
      navigate('/', { replace: true })
    } catch (error) {
      let hasFieldError = false
      for (const [serverField, formField] of [
        ['full_name', 'fullName'],
        ['email', 'email'],
        ['password', 'password'],
      ] as const) {
        const message = apiFieldError(error, serverField)
        if (message) {
          setError(formField, { message })
          hasFieldError = true
        }
      }
      if (!hasFieldError) {
        setError('root', {
          message:
            error instanceof Error
              ? error.message
              : 'Unable to create your account right now.',
        })
      }
    }
  })

  return (
    <AuthPageLayout
      eyebrow="GET STARTED"
      title="Create your account"
      description="Set up your secure sign-in to get started with Biashara Pulse."
      footer={
        <>
          Already have an account?{' '}
          <Link
            className="font-semibold text-emerald-700 hover:text-emerald-900"
            to="/login"
          >
            Sign in
          </Link>
        </>
      }
    >
      <form className="mt-8 space-y-4" onSubmit={submit} noValidate>
        <div>
          <label className="field-label" htmlFor="full-name">
            Full name
          </label>
          <input
            autoComplete="name"
            className="field-input"
            id="full-name"
            placeholder="Your name"
            {...register('fullName')}
          />
          {errors.fullName && (
            <p className="field-error" role="alert">
              {errors.fullName.message}
            </p>
          )}
        </div>
        <div>
          <label className="field-label" htmlFor="signup-email">
            Email address
          </label>
          <input
            autoComplete="email"
            className="field-input"
            id="signup-email"
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
          <label className="field-label" htmlFor="signup-password">
            Password
          </label>
          <input
            autoComplete="new-password"
            className="field-input"
            id="signup-password"
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
          <label className="field-label" htmlFor="password-confirm">
            Confirm password
          </label>
          <input
            autoComplete="new-password"
            className="field-input"
            id="password-confirm"
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
          className="button-primary mt-2 w-full justify-center"
          disabled={isSubmitting}
          type="submit"
        >
          {isSubmitting ? 'Creating account…' : 'Create account'}
        </button>
      </form>
    </AuthPageLayout>
  )
}
