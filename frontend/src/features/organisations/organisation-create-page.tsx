import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { apiClient } from '../../shared/api/client'
import { useOrganisation } from './organisation-context'

const schema = z.object({
  name: z.string().trim().min(2, 'Enter an organisation name.').max(150),
  sector: z.enum(['retail', 'wholesale', 'schools', 'pharmacy']),
  country_code: z.string().regex(/^[A-Za-z]{2}$/, 'Use a 2-letter country code.'),
  currency: z.string().regex(/^[A-Za-z]{3}$/, 'Use a 3-letter currency code.'),
  timezone: z.string().min(1, 'Enter a timezone.').max(64),
})

type Values = z.infer<typeof schema>

export function OrganisationCreatePage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { selectOrganisation } = useOrganisation()
  const createOrganisation = useMutation({
    mutationFn: (values: Values) => apiClient.createOrganisation(values),
    onSuccess: async (organisation) => {
      selectOrganisation(organisation.id)
      await queryClient.invalidateQueries({ queryKey: ['organisations'] })
      navigate('/', { replace: true })
    },
  })
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: '',
      sector: 'retail',
      country_code: 'KE',
      currency: 'KES',
      timezone: 'Africa/Nairobi',
    },
  })

  const submit = handleSubmit(async (values) => {
    await createOrganisation.mutateAsync(values)
  })

  return (
    <div className="page-content">
      <p className="eyebrow">NEW WORKSPACE</p>
      <h1 className="page-title">Create an organisation</h1>
      <p className="page-description">
        Your account will become the owner of this organisation.
      </p>

      <form className="form-panel mt-8" onSubmit={submit} noValidate>
        <div className="form-grid">
          <div className="form-field-wide">
            <label className="field-label" htmlFor="organisation-name">
              Organisation name
            </label>
            <input
              className="field-input"
              id="organisation-name"
              placeholder="e.g. Greenview Traders"
              {...register('name')}
            />
            {errors.name && <p className="field-error">{errors.name.message}</p>}
          </div>
          <div>
            <label className="field-label" htmlFor="sector">
              Business type
            </label>
            <select className="field-input" id="sector" {...register('sector')}>
              <option value="retail">Retail</option>
              <option value="wholesale">Wholesale</option>
              <option value="schools">Schools</option>
              <option value="pharmacy">Pharmacy</option>
            </select>
            {errors.sector && (
              <p className="field-error">{errors.sector.message}</p>
            )}
          </div>
          <div>
            <label className="field-label" htmlFor="timezone">
              Timezone
            </label>
            <input
              className="field-input"
              id="timezone"
              {...register('timezone')}
            />
            {errors.timezone && (
              <p className="field-error">{errors.timezone.message}</p>
            )}
          </div>
          <div>
            <label className="field-label" htmlFor="country-code">
              Country code
            </label>
            <input
              className="field-input"
              id="country-code"
              maxLength={2}
              {...register('country_code')}
            />
            {errors.country_code && (
              <p className="field-error">{errors.country_code.message}</p>
            )}
          </div>
          <div>
            <label className="field-label" htmlFor="currency">
              Currency
            </label>
            <input
              className="field-input"
              id="currency"
              maxLength={3}
              {...register('currency')}
            />
            {errors.currency && (
              <p className="field-error">{errors.currency.message}</p>
            )}
          </div>
        </div>
        {createOrganisation.isError && (
          <p className="form-alert mt-5" role="alert">
            {createOrganisation.error.message}
          </p>
        )}
        {createOrganisation.isSuccess && (
          <p className="form-success mt-5" role="status">
            Organisation created. Opening your workspace…
          </p>
        )}
        <div className="form-actions">
          <Link className="button-secondary" to="/organisations">
            Cancel
          </Link>
          <button
            className="button-primary"
            disabled={isSubmitting || createOrganisation.isPending}
            type="submit"
          >
            {createOrganisation.isPending ? 'Creating…' : 'Create organisation'}
          </button>
        </div>
      </form>
    </div>
  )
}
