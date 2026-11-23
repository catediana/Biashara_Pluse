import { useQueryClient } from '@tanstack/react-query'
import {
  BrowserRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
} from 'react-router-dom'

import { useAuth } from '../features/auth/auth-context'
import { ForgotPasswordPage } from '../features/auth/forgot-password-page'
import { LoginPage } from '../features/auth/login-page'
import { ResetPasswordPage } from '../features/auth/reset-password-page'
import { SignupPage } from '../features/auth/signup-page'
import {
  DashboardPage,
  WorkspacePlaceholder,
} from '../features/retail/dashboard-page'
import { AppLayout } from './layout/app-layout'

const CURRENT_USER_KEY = ['auth', 'current-user']

function AuthGate() {
  const { user, isLoading, error } = useAuth()
  const queryClient = useQueryClient()

  if (isLoading) {
    return (
      <main className="grid min-h-screen place-items-center">
        <p role="status" className="text-sm text-slate-500">
          Checking your session…
        </p>
      </main>
    )
  }

  if (error) {
    return (
      <main className="grid min-h-screen place-items-center px-6">
        <section className="panel max-w-md p-8 text-center">
          <h1 className="text-xl font-semibold text-slate-900">
            We couldn’t reach Biashara Pulse
          </h1>
          <p className="mt-2 text-sm text-slate-600">
            Check your connection and try again.
          </p>
          <button
            className="button-primary mt-6"
            onClick={() =>
              queryClient.invalidateQueries({ queryKey: CURRENT_USER_KEY })
            }
          >
            Try again
          </button>
        </section>
      </main>
    )
  }

  return user ? <Outlet /> : <Navigate to="/login" replace />
}

function GuestGate() {
  const { user, isLoading } = useAuth()
  if (isLoading) return null
  return user ? <Navigate to="/" replace /> : <Outlet />
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<GuestGate />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route
          path="/reset-password/:uidb64/:token"
          element={<ResetPasswordPage />}
        />
      </Route>
      <Route element={<AuthGate />}>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="workspace" element={<WorkspacePlaceholder />} />
          <Route path="sales" element={<WorkspacePlaceholder />} />
          <Route path="inventory" element={<WorkspacePlaceholder />} />
          <Route path="customers" element={<WorkspacePlaceholder />} />
          <Route path="reports" element={<WorkspacePlaceholder />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
