import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { z } from 'zod'

import { apiClient } from '../../shared/api/client'
import type { StaffMember } from '../../shared/types/api'
import { useOrganisation } from './organisation-context'

const staffSchema = z
  .object({
    email: z.string().trim().email('Enter a valid email address.'),
    role_id: z.string().uuid('Choose a role.'),
    all_branches: z.boolean(),
    branch_ids: z.array(z.string().uuid()),
  })
  .refine(
    (values) => values.all_branches || values.branch_ids.length > 0,
    {
      path: ['branch_ids'],
      message: 'Choose at least one branch or enable all branches.',
    },
  )
type StaffValues = z.infer<typeof staffSchema>

export function StaffPage() {
  const { organisationId } = useOrganisation()
  const queryClient = useQueryClient()
  const [allBranches, setAllBranches] = useState(true)
  const staffKey = ['organisation', organisationId, 'staff']
  const rolesKey = ['organisation', organisationId, 'roles']
  const staff = useQuery({
    queryKey: staffKey,
    queryFn: apiClient.listStaff,
    enabled: Boolean(organisationId),
  })
  const roles = useQuery({
    queryKey: rolesKey,
    queryFn: apiClient.listRoles,
    enabled: Boolean(organisationId),
  })
  const branches = useQuery({
    queryKey: ['organisation', organisationId, 'branches'],
    queryFn: apiClient.listBranches,
    enabled: Boolean(organisationId),
  })
  const addMember = useMutation({
    mutationFn: (values: StaffValues) => apiClient.createStaffMember(values),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: staffKey })
    },
  })
  const updateMember = useMutation({
    mutationFn: ({
      id,
      values,
    }: {
      id: string
      values: Parameters<typeof apiClient.updateStaffMember>[1]
    }) => apiClient.updateStaffMember(id, values),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: staffKey })
    },
  })
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<StaffValues>({
    resolver: zodResolver(staffSchema),
    defaultValues: {
      email: '',
      role_id: '',
      all_branches: true,
      branch_ids: [],
    },
  })

  const availableRoles =
    roles.data?.results.filter((role) => role.is_active && !role.is_system) ?? []

  const submit = handleSubmit(async (values) => {
    await addMember.mutateAsync(values)
    reset({ email: '', role_id: '', all_branches: true, branch_ids: [] })
    setAllBranches(true)
  })

  function update(member: StaffMember, values: Parameters<typeof apiClient.updateStaffMember>[1]) {
    updateMember.mutate({ id: member.id, values })
  }

  if (!organisationId) {
    return (
      <ManagementPrompt
        title="Select an organisation"
        message="Choose a workspace before managing its staff."
      />
    )
  }

  return (
    <div className="page-content">
      <p className="eyebrow">PEOPLE & ACCESS</p>
      <h1 className="page-title">Staff management</h1>
      <p className="page-description">
        Add existing Biashara Pulse accounts and manage their organisation role.
      </p>

      <section className="form-panel mt-8">
        <div>
          <h2 className="panel-title">Add a staff member</h2>
          <p className="panel-description">
            The person must already have a Biashara Pulse account.
          </p>
        </div>
        {roles.isPending ? (
          <p className="mt-5 text-sm text-slate-500" role="status">
            Loading available roles…
          </p>
        ) : roles.isError ? (
          <div className="state-error mt-5" role="alert">
            <p>Roles could not be loaded: {roles.error.message}</p>
            <button
              className="text-link mt-2"
              onClick={() => void roles.refetch()}
              type="button"
            >
              Try again
            </button>
          </div>
        ) : availableRoles.length === 0 ? (
          <div className="empty-inline mt-5">
            <p>No assignable roles are available yet.</p>
            <Link className="text-link" to="/roles">
              Create a role
            </Link>
          </div>
        ) : (
          <form className="staff-form mt-5" onSubmit={submit} noValidate>
            <div>
              <label className="field-label" htmlFor="staff-email">
                Account email
              </label>
              <input
                autoComplete="email"
                className="field-input"
                id="staff-email"
                placeholder="colleague@business.com"
                {...register('email')}
              />
              {errors.email && (
                <p className="field-error" role="alert">
                  {errors.email.message}
                </p>
              )}
            </div>
            <div>
              <label className="field-label" htmlFor="staff-role">
                Role
              </label>
              <select
                className="field-input"
                id="staff-role"
                {...register('role_id')}
              >
                <option value="">Select a role</option>
                {availableRoles.map((role) => (
                  <option key={role.id} value={role.id}>
                    {role.name}
                  </option>
                ))}
              </select>
              {errors.role_id && (
                <p className="field-error" role="alert">
                  {errors.role_id.message}
                </p>
              )}
            </div>
            <label className="check-field">
              <input
                type="checkbox"
                {...register('all_branches', {
                  onChange: (event) => setAllBranches(event.target.checked),
                })}
              />
              Access to all branches
            </label>
            {!branches.isPending && !branches.isError && branches.data.results.length > 0 && (
              <fieldset className="branch-fieldset staff-form-wide">
                <legend className="field-label">Limit access to branches</legend>
                <div className="permission-grid">
                  {branches.data.results.map((branch) => (
                    <label className="check-field" key={branch.id}>
                      <input
                        disabled={allBranches}
                        type="checkbox"
                        value={branch.id}
                        {...register('branch_ids')}
                      />
                      {branch.name}
                    </label>
                  ))}
                </div>
              </fieldset>
            )}
            {branches.isError && (
              <p className="form-alert staff-form-wide" role="alert">
                Branches could not be loaded: {branches.error.message}
              </p>
            )}
            {errors.branch_ids && (
              <p className="field-error staff-form-wide" role="alert">
                {errors.branch_ids.message}
              </p>
            )}
            {addMember.isError && (
              <p className="form-alert staff-form-wide" role="alert">
                {addMember.error.message}
              </p>
            )}
            {addMember.isSuccess && (
              <p className="form-success staff-form-wide" role="status">
                Staff member added successfully.
              </p>
            )}
            <button
              className="button-primary staff-form-wide"
              disabled={isSubmitting || addMember.isPending}
              type="submit"
            >
              {addMember.isPending ? 'Adding staff member…' : 'Add staff member'}
            </button>
          </form>
        )}
      </section>

      <section className="mt-9">
        <div className="section-heading management-heading">
          <div>
            <p className="eyebrow">ORGANISATION MEMBERS</p>
            <h2>Staff list</h2>
          </div>
          <span className="section-hint">
            {staff.data ? `${staff.data.results.length} members` : ''}
          </span>
        </div>
        {staff.isPending ? (
          <p className="state-card mt-4" role="status">
            Loading staff…
          </p>
        ) : staff.isError ? (
          <section className="state-card state-error mt-4" role="alert">
            <h2>Staff could not be loaded</h2>
            <p>{staff.error.message}</p>
            <button
              className="button-primary mt-4"
              onClick={() => void staff.refetch()}
              type="button"
            >
              Try again
            </button>
          </section>
        ) : staff.data.results.length === 0 ? (
          <section className="state-card mt-4">
            <h2 className="text-base font-semibold text-slate-800">
              No staff members yet
            </h2>
            <p className="mt-2 text-sm text-slate-500">
              Add a registered user above to give them access to this organisation.
            </p>
          </section>
        ) : (
          <div className="table-card mt-4">
            <div className="staff-table-head">
              <span>TEAM MEMBER</span>
              <span>ROLE</span>
              <span>STATUS</span>
              <span>BRANCH ACCESS</span>
            </div>
            {staff.data.results.map((member) => (
              <article className="staff-table-row" key={member.id}>
                <div className="staff-person">
                  <span className="avatar">
                    {(member.user.first_name[0] ?? member.user.email[0]).toUpperCase()}
                  </span>
                  <span>
                    <strong>
                      {[member.user.first_name, member.user.last_name]
                        .filter(Boolean)
                        .join(' ') || member.user.email}
                    </strong>
                    <small>{member.user.email}</small>
                  </span>
                </div>
                <div>
                  {member.role.name}
                  {member.role.is_system && (
                    <span className="table-hint">System role</span>
                  )}
                  {!member.role.is_system && (
                    <select
                      aria-label={`Role for ${member.user.email}`}
                      className="table-select"
                      disabled={updateMember.isPending}
                      onChange={(event) => {
                        if (event.target.value) {
                          update(member, { role_id: event.target.value })
                        }
                      }}
                      value={member.role.id}
                    >
                      {!availableRoles.some((role) => role.id === member.role.id) && (
                        <option value={member.role.id}>{member.role.name}</option>
                      )}
                      {availableRoles.map((role) => (
                        <option key={role.id} value={role.id}>
                          {role.name}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
                <select
                  aria-label={`Status for ${member.user.email}`}
                  className="table-select"
                  disabled={updateMember.isPending}
                  onChange={(event) =>
                    update(member, {
                      status: event.target.value as StaffMember['status'],
                    })
                  }
                  value={member.status}
                >
                  <option value="active">Active</option>
                  <option value="invited">Invited</option>
                  <option value="suspended">Suspended</option>
                </select>
                <label className="table-check">
                  {member.all_branches
                    ? 'All branches'
                    : `Limited to ${member.branch_ids.length} branch${member.branch_ids.length === 1 ? '' : 'es'}`}
                </label>
              </article>
            ))}
            {updateMember.isError && (
              <p className="form-alert m-4" role="alert">
                {updateMember.error.message}
              </p>
            )}
          </div>
        )}
      </section>
    </div>
  )
}

function ManagementPrompt({
  title,
  message,
}: {
  title: string
  message: string
}) {
  return (
    <section className="page-content state-card">
      <h1 className="text-lg font-semibold text-slate-900">{title}</h1>
      <p className="mt-2 text-sm text-slate-500">{message}</p>
      <Link className="button-primary mt-5" to="/organisations">
        Choose organisation
      </Link>
    </section>
  )
}
