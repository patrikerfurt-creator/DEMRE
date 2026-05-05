import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Loader2, Save } from 'lucide-react'
import api from '@/lib/api'
import type { CompanySettings } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { toast } from '@/hooks/use-toast'

const schema = z.object({
  company_name: z.string().min(1),
  company_street: z.string().min(1),
  company_zip: z.string().min(1),
  company_city: z.string().min(1),
  company_country: z.string().min(2).max(2),
  company_phone: z.string().optional(),
  company_email: z.string().optional(),
  company_vat_id: z.string().optional(),
  company_tax_number: z.string().optional(),
  company_iban: z.string().optional(),
  company_bic: z.string().optional(),
  company_bank_name: z.string().optional(),
  datev_berater_number: z.string().optional(),
  datev_mandant_number: z.string().optional(),
})
type FormData = z.infer<typeof schema>

export function SettingsPage() {
  const queryClient = useQueryClient()

  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.get<CompanySettings>('/settings').then((r) => r.data),
  })

  const { register, handleSubmit, reset, formState: { isDirty } } = useForm<FormData>({
    resolver: zodResolver(schema),
    values: settings ? {
      company_name: settings.company_name,
      company_street: settings.company_street,
      company_zip: settings.company_zip,
      company_city: settings.company_city,
      company_country: settings.company_country,
      company_phone: settings.company_phone || '',
      company_email: settings.company_email || '',
      company_vat_id: settings.company_vat_id || '',
      company_tax_number: settings.company_tax_number || '',
      company_iban: settings.company_iban || '',
      company_bic: settings.company_bic || '',
      company_bank_name: settings.company_bank_name || '',
      datev_berater_number: settings.datev_berater_number || '',
      datev_mandant_number: settings.datev_mandant_number || '',
    } : undefined,
  })

  const saveMutation = useMutation({
    mutationFn: (data: FormData) => api.put('/settings', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      toast({ title: 'Einstellungen gespeichert' })
    },
    onError: (err: any) => {
      toast({ title: 'Fehler', description: err?.response?.data?.detail, variant: 'destructive' })
    },
  })

  if (isLoading) return <div className="p-6 text-muted-foreground">Lädt...</div>

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Einstellungen</h1>
        <p className="text-sm text-slate-500 mt-1">Firmendaten und Systemkonfiguration</p>
      </div>

      <form onSubmit={handleSubmit((data) => saveMutation.mutate(data))} className="space-y-6">
        {/* Company */}
        <Card>
          <CardHeader>
            <CardTitle>Firmendaten</CardTitle>
            <CardDescription>Diese Daten erscheinen auf Rechnungen und im ZUGFeRD-XML.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Firmenname *</Label>
              <Input {...register('company_name')} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Straße / Hausnummer *</Label>
                <Input {...register('company_street')} />
              </div>
              <div className="space-y-2">
                <Label>Ländercode *</Label>
                <Input {...register('company_country')} maxLength={2} placeholder="DE" />
              </div>
              <div className="space-y-2">
                <Label>PLZ *</Label>
                <Input {...register('company_zip')} />
              </div>
              <div className="space-y-2">
                <Label>Ort *</Label>
                <Input {...register('company_city')} />
              </div>
              <div className="space-y-2">
                <Label>Telefon</Label>
                <Input {...register('company_phone')} placeholder="+49 69 123456" />
              </div>
              <div className="space-y-2">
                <Label>E-Mail</Label>
                <Input {...register('company_email')} placeholder="info@demme-immobilien.de" />
              </div>
              <div className="space-y-2">
                <Label>USt-IdNr.</Label>
                <Input {...register('company_vat_id')} placeholder="DE123456789" />
              </div>
              <div className="space-y-2">
                <Label>Steuernummer</Label>
                <Input {...register('company_tax_number')} />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Bank */}
        <Card>
          <CardHeader>
            <CardTitle>Bankverbindung</CardTitle>
            <CardDescription>Wird auf Rechnungen und im SEPA-Export verwendet.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>IBAN</Label>
                <Input {...register('company_iban')} placeholder="DE89370400440532013000" />
              </div>
              <div className="space-y-2">
                <Label>BIC</Label>
                <Input {...register('company_bic')} placeholder="COBADEFFXXX" />
              </div>
              <div className="col-span-2 space-y-2">
                <Label>Kreditinstitut</Label>
                <Input {...register('company_bank_name')} />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* DATEV */}
        <Card>
          <CardHeader>
            <CardTitle>DATEV-Export</CardTitle>
            <CardDescription>Berater- und Mandantennummer für den DATEV Buchungsstapel-Export.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Beraternummer</Label>
                <Input {...register('datev_berater_number')} placeholder="12345" />
              </div>
              <div className="space-y-2">
                <Label>Mandantennummer</Label>
                <Input {...register('datev_mandant_number')} placeholder="67890" />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Invoice numbering */}
        <Card>
          <CardHeader>
            <CardTitle>Rechnungsnummern</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Format: <span className="font-mono font-medium text-slate-700">JJJJ-NNNN</span>
              &nbsp;— z.&nbsp;B. <span className="font-mono font-medium text-slate-700">2026-0311</span>,{' '}
              <span className="font-mono font-medium text-slate-700">2027-0001</span>.
              Die Nummerierung setzt sich jährlich zurück.
            </p>
          </CardContent>
        </Card>

        <div className="flex justify-end">
          <Button type="submit" disabled={saveMutation.isPending}>
            {saveMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            Einstellungen speichern
          </Button>
        </div>
      </form>
    </div>
  )
}
