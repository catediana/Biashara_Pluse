import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { apiClient } from '../../shared/api/client'
import type { RoleSummary } from '../../shared/types/api'
import { useOrganisation } from './organisation-context'

const MODULE_LABELS: Record<string, string> = {
  platform: 'Platform',
  retail: 'Retail',
  wholesale: 'Wholesale',
  schools: 'Schools',
  pharmacy: 'Pharmacy',
}

export function RolesPage() {
  const { organisationId } = useOrganisation()
  const queryClient = useQueryClient()
  const rolesKey = ['organisation', organisationId, 'roles']
  const permissionsKey = ['organisation', organisationId, 'permissions']
  const roles = useQuery({
    queryKey: rolesKey,
    queryFn: apiClient.listRoles,
    enabled: Boolean(organisationId),
  })
  const permissions = useQuery({
    queryKey: permissionsKey,
    queryFn: apiClient.listPermissions,
    enabled: Boolean(organisationId),
  })
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([])
  const [editing, setEditing] = useState<RoleSummary | null>(null)

  const saveRole = useMutation({
    mutationFn: async () => {
      const payload = {
        name: name.trim(),
        description: description.trim(),
        permission_ids: selectedPermissions,
      }
      return editing
        ? apiClient.updateRole(editing.id, payload)
        : apiClient.createRole(payload)
    },
    onSuccess: async () => {
      resetForm()
      await queryClient.invalidateQueries({ queryKey: rolesKey })
    },
  })
  const changeRoleStatus = useMutation({
    mutationFn: ({ role, is_active }: { role: RoleSummary; is_active: boolean }) =>
      apiClient.updateRole(role.id, { is_active }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: rolesKey })
    },
  })

  function resetForm() {
    setEditing(null)
    setName('')
    setDescription('')
    setSelectedPermissions([])
  }

  function editRole(role: RoleSummary) {
    setEditing(role)
    setName(role.name)
    setDescription(role.description)
    setSelectedPermissions(role.permissions.map((permission) => permission.id))
  }

  function togglePermission(id: string) {
    setSelectedPermissions((current) =>
      current.includes(id)
        ? current.filter((permissionId) => permissionId !== id)
        : [...current, id],
    )
  }

  if (!organisationId) {
    return (
      <section className="page-content state-card">
        <h1 className="text-lg font-semibold text-slate-900">
          Select an organisation
        </h1>
        <p className="mt-2 text-sm text-slate-500">
          Choose a workspace before managing its roles.
        </p>
        <Link className="button-primary mt-5" to="/organisations">
          Choose organisation
        </Link>
      </section>
    )
  }

  return (
    <div className="page-content">
      <p className="eyebrow">ACCESS CONTROL</p>
      <h1 className="page-title">Roles & permissions</h1>
      <p className="page-description">
        Define what each team role can access in this organisation.
      </p>

      <section className="form-panel mt-8">
        <div>
          <h2 className="panel-title">
            {editing ? `Edit ${editing.name}` : 'Create a role'}
          </h2>
          <p className="panel-description">
            System roles are protected and cannot be changed.
          </p>
        </div>
        {permissions.isPending ? (
          <p className="mt-5 text-sm text-slate-500" role="status">
            Loading permissions…
          </p>
        ) : permissions.isError ? (
          <div className="state-error mt-5" role="alert">
            <p>Permissions could not be loaded: {permissions.error.message}</p>
            <button
              className="text-link mt-2"
              onClick={() => void permissions.refetch()}
              type="button"
            >
              Try again
            </button>
          </div>
        ) : (
          <form
            className="mt-5"
            onSubmit={(event) => {
              event.preventDefault()
              saveRole.mutate()
            }}
          >
            <div className="form-grid">
              <div>
                <label className="field-label" htmlFor="role-name">
                  Role name
                </label>
                <input
                  className="field-input"
                  id="role-name"
                  maxLength={80}
                  onChange={(event) => setName(event.target.value)}
                  required
                  value={name}
                />
              </div>
              <div>
                <label className="field-label" htmlFor="role-description">
                  Description
                </label>
                <input
                  className="field-input"
                  id="role-description"
                  maxLength={255}
                  onChange={(event) => setDescription(event.target.value)}
                  value={description}
                />
              </div>
            </div>
            <fieldset className="permission-fieldset mt-6">
              <legend className="field-label">Permissions</legend>
              {permissions.data.results.length === 0 ? (
                <p className="empty-inline mt-2">
                  No permissions are configured yet.
                </p>
              ) : (
                Object.entries(
                  permissions.data.results.reduce<
                    Record<string, typeof permissions.data.results>
                  >((groups, permission) => {
                    ;(groups[permission.module] ??= []).push(permission)
                    return groups
                  }, {}),
                ).map(([module, modulePermissions]) => (
                  <div className="permission-group" key={module}>
                    <h3>{MODULE_LABELS[module] ?? module}</h3>
                    <div className="permission-grid">
                      {modulePermissions.map((permission) => (
                        <label className="check-field" key={permission.id}>
                          <input
                            checked={selectedPermissions.includes(permission.id)}
                            onChange={() => togglePermission(permission.id)}
                            type="checkbox"
                          />
                          <span>
                            <strong>{permission.name}</strong>
                            <small>{permission.codename}</small>
                          </span>
                        </label>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </fieldset>
            {saveRole.isError && (
              <p className="form-alert mt-5" role="alert">
                {saveRole.error.message}
              </p>
            )}
            {saveRole.isSuccess && (
              <p className="form-success mt-5" role="status">
                Role saved successfully.
              </p>
            )}
            <div className="form-actions">
              {editing && (
                <button
                  className="button-secondary"
                  onClick={resetForm}
                  type="button"
                >
                  Cancel edit
                </button>
              )}
              <button
                className="button-primary"
                disabled={saveRole.isPending || !name.trim()}
                type="submit"
              >
                {saveRole.isPending
                  ? 'Saving…'
                  : editing
                    ? 'Save changes'
                    : 'Create role'}
              </button>
            </div>
          </form>
        )}
      </section>

      <section className="mt-9">
        <div className="section-heading management-heading">
          <div>
            <p className="eyebrow">ORGANISATION ROLES</p>
            <h2>Available roles</h2>
          </div>
          <span className="section-hint">
            {roles.data ? `${roles.data.results.length} roles` : ''}
          </span>
        </div>
        {roles.isPending ? (
          <p className="state-card mt-4" role="status">
            Loading roles…
          </p>
        ) : roles.isError ? (
          <section className="state-card state-error mt-4" role="alert">
            <h2>Roles could not be loaded</h2>
            <p>{roles.error.message}</p>
            <button
              className="button-primary mt-4"
              onClick={() => void roles.refetch()}
              type="button"
            >
              Try again
            </button>
          </section>
        ) : roles.data.results.length === 0 ? (
          <section className="state-card mt-4">
            <h2 className="text-base font-semibold text-slate-800">
              No roles yet
            </h2>
            <p className="mt-2 text-sm text-slate-500">
              Create a role to define access for your staff.
            </p>
          </section>
        ) : (
          <div className="role-grid mt-4">
            {roles.data.results.map((role) => (
              <article className="role-card" key={role.id}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-900">
                      {role.name}
                    </h3>
                    <p className="mt-1 text-xs text-slate-500">
                      {role.description || 'No description'}
                    </p>
                  </div>
                  <span
                    className={
                      role.is_active ? 'status-badge' : 'status-badge status-muted'
                    }
                  >
                    {role.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
                <p className="mt-4 text-xs text-slate-500">
                  {role.permissions.length} permissions
                  {role.is_system ? ' · System role' : ''}
                </p>
                {role.permissions.length > 0 && (
                  <ul className="role-permissions">
                    {role.permissions.slice(0, 5).map((permission) => (
                      <li key={permission.id}>{permission.name}</li>
                    ))}
                    {role.permissions.length > 5 && (
                      <li>+{role.permissions.length - 5} more</li>
                    )}
                  </ul>
                )}
                {!role.is_system && (
                  <div className="role-actions">
                    <button
                      className="text-link"
                      onClick={() => editRole(role)}
                      type="button"
                    >
                      Edit
                    </button>
                    <button
                      className="text-link"
                      disabled={changeRoleStatus.isPending}
                      onClick={() =>
                        changeRoleStatus.mutate({
                          role,
                          is_active: !role.is_active,
                        })
                      }
                      type="button"
                    >
                      {role.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
        {changeRoleStatus.isError && (
          <p className="form-alert mt-4" role="alert">
            {changeRoleStatus.error.message}
          </p>
        )}
      </section>
    </div>
  )
}
