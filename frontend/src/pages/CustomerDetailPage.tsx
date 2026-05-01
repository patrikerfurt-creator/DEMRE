import { useState } from 'react'
import { useWatch } from 'react-hook-form'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { ArrowLeft, Building2, Phone, Mail, CreditCard, Pencil, Loader2 } from 'lucide-react'
import api from '@/lib/api'
import type { Customer, Contract, Invoice } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { toast } from '@/hooks/use-toast'
import { formatDate, formatCurrency, INVOICE_STATUS_LABELS, INVOICE_STATUS_COLORS, CONTRACT_STATUS_LABELS, validateIban, lookupBicFromIban } from '@/lib/utils'

const schema = z.object({
  customer_number: z.string().optional(),
  customer_type: z.enum(['weg', 'company', 'person']).default('weg'),
  company_name: z.string().optional(),
  salutation: z.string().optional(),
  first_name: z.string().optional(),
  last_name: z.string().optional(),
  address_line1: z.string().optional(),
  address_line2: z.string().optional(),
  postal_code: z.string().optional(),
  city: z.string().optional(),
  country_code: z.string().default('DE'),
  email: z.string().email().optional().or(z.literal('')),
  phone: z.string().optional(),
  vat_id: z.string().optional(),
  iban: z.string().optional().refine(
    (val) => !val || validateIban(val),
    { message: 'Ungültige IBAN' }
  ),
  bic: z.string().optional(),
  bank_name: z.string().optional(),
  account_holder: z.string().optional(),
  datev_account_number: z.string().optional(),
  notes: z.string().optional(),
  is_active: z.boolean().default(true),
})
type FormData = z.infer<typeof schema>

export function CustomerDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [bicLoading, setBicLoading] = useState(false)

  const { data: customer, isLoading } = useQuery({
    queryKey: ['customer', id],
    queryFn: () => api.get<Customer>(`/customers/${id}`).then((r) => r.data),
    enabled: !!id,
  })

  const { data: contracts } = useQuery({
    queryKey: ['contracts', 'customer', id],
    queryFn: () => api.get<Contract[]>(`/contracts?customer_id=${id}&page_size=100`).then((r) => r.data),
    enabled: !!id,
  })

  const { data: invoices } = useQuery({
    queryKey: ['invoices', 'customer', id],
    queryFn: () => api.get<Invoice[]>(`/invoices?customer_id=${id}&page_size=100`).then((r) => r.data),
    enabled: !!id,
  })

  const { register, handleSubmit, reset, control, setValue, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  })
  const customerType = useWatch({ control, name: 'customer_type' })

  const updateMutation = useMutation({
    mutationFn: (data: FormData) => api.put(`/customers/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customer', id] })
      queryClient.invalidateQueries({ queryKey: ['customers'] })
      setDialogOpen(false)
      toast({ title: 'Kunde aktualisiert' })
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail
      const msg = typeof detail === 'string' ? detail : err?.message || 'Unbekannter Fehler'
      toast({ title: 'Fehler beim Speichern', description: msg, variant: 'destructive' })
    },
  })

  function openEdit() {
    if (!customer) return
    reset({
      customer_number: customer.customer_number,
      customer_type: customer.customer_type || 'weg',
      company_name: customer.company_name || '',
      salutation: customer.salutation || '',
      first_name: customer.first_name || '',
      last_name: customer.last_name || '',
      address_line1: customer.address_line1 || '',
      address_line2: customer.address_line2 || '',
      postal_code: customer.postal_code || '',
      city: customer.city || '',
      country_code: customer.country_code,
      email: customer.email || '',
      phone: customer.phone || '',
      vat_id: customer.vat_id || '',
      iban: customer.iban || '',
      bic: customer.bic || '',
      bank_name: customer.bank_name || '',
      account_holder: customer.account_holder || '',
      datev_account_number: customer.datev_account_number || '',
      notes: customer.notes || '',
      is_active: customer.is_active,
    })
    setDialogOpen(true)
  }

  if (isLoading) {
    return <div className="p-6 text-muted-foreground">Lädt...</div>
  }
  if (!customer) {
    return <div className="p-6 text-muted-foreground">Kunde nicht gefunden</div>
  }

  const displayName = customer.company_name
    || `${customer.first_name || ''} ${customer.last_name || ''}`.trim()
    || customer.customer_number

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/customers')}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{displayName}</h1>
          <p className="text-sm text-slate-500">Kundennummer: {customer.customer_number}</p>
        </div>
        <Badge variant={customer.is_active ? 'default' : 'secondary'} className="ml-auto">
          {customer.is_active ? 'Aktiv' : 'Inaktiv'}
        </Badge>
        <Button variant="outline" size="sm" onClick={openEdit}>
          <Pencil className="h-4 w-4 mr-2" /> Bearbeiten
        </Button>
      </div>

      {/* Customer Info */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Building2 className="h-4 w-4" /> Adresse
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm space-y-1">
            {customer.company_name && <div className="font-medium">{customer.company_name}</div>}
            {(customer.first_name || customer.last_name) && (
              <div>{[customer.salutation, customer.first_name, customer.last_name].filter(Boolean).join(' ')}</div>
            )}
            {customer.address_line1 && <div>{customer.address_line1}</div>}
            {customer.address_line2 && <div>{customer.address_line2}</div>}
            {(customer.postal_code || customer.city) && (
              <div>{[customer.postal_code, customer.city].filter(Boolean).join(' ')}</div>
            )}
            <div className="text-muted-foreground">{customer.country_code}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Phone className="h-4 w-4" /> Kontakt
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm space-y-1">
            {customer.email && <div className="flex items-center gap-2"><Mail className="h-3 w-3" />{customer.email}</div>}
            {customer.phone && <div className="flex items-center gap-2"><Phone className="h-3 w-3" />{customer.phone}</div>}
            {customer.vat_id && <div>USt-IdNr.: {customer.vat_id}</div>}
            {customer.tax_number && <div>Steuernummer: {customer.tax_number}</div>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <CreditCard className="h-4 w-4" /> Bankverbindung
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm space-y-1">
            {customer.bank_name && <div className="font-medium">{customer.bank_name}</div>}
            {customer.account_holder && <div>{customer.account_holder}</div>}
            {customer.iban && <div className="font-mono">{customer.iban}</div>}
            {customer.bic && <div className="font-mono">{customer.bic}</div>}
            {customer.datev_account_number && (
              <div className="text-muted-foreground">DATEV: {customer.datev_account_number}</div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="contracts">
        <TabsList>
          <TabsTrigger value="contracts">
            Verträge ({Array.isArray(contracts) ? contracts.length : 0})
          </TabsTrigger>
          <TabsTrigger value="invoices">
            Rechnungen ({Array.isArray(invoices) ? invoices.length : 0})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="contracts">
          <div className="border rounded-lg mt-2">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Vertragsnummer</TableHead>
                  <TableHead>Objekt</TableHead>
                  <TableHead>Start</TableHead>
                  <TableHead>Ende</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Positionen</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {!Array.isArray(contracts) || contracts.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                      Keine Verträge vorhanden
                    </TableCell>
                  </TableRow>
                ) : (
                  contracts.map((c) => (
                    <TableRow
                      key={c.id}
                      className="cursor-pointer"
                      onClick={() => navigate(`/contracts/${c.id}`)}
                    >
                      <TableCell className="font-mono text-sm">{c.contract_number}</TableCell>
                      <TableCell>{c.property_ref || '–'}</TableCell>
                      <TableCell>{formatDate(c.start_date)}</TableCell>
                      <TableCell>{formatDate(c.end_date)}</TableCell>
                      <TableCell>
                        <Badge variant={c.status === 'active' ? 'default' : 'secondary'}>
                          {CONTRACT_STATUS_LABELS[c.status]}
                        </Badge>
                      </TableCell>
                      <TableCell>{c.items.length}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        <TabsContent value="invoices">
          <div className="border rounded-lg mt-2">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nummer</TableHead>
                  <TableHead>Datum</TableHead>
                  <TableHead>Fällig</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Betrag</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {!Array.isArray(invoices) || invoices.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                      Keine Rechnungen vorhanden
                    </TableCell>
                  </TableRow>
                ) : (
                  invoices.map((inv) => (
                    <TableRow
                      key={inv.id}
                      className="cursor-pointer"
                      onClick={() => navigate(`/invoices/${inv.id}`)}
                    >
                      <TableCell className="font-mono text-sm">{inv.invoice_number}</TableCell>
                      <TableCell>{formatDate(inv.invoice_date)}</TableCell>
                      <TableCell>{formatDate(inv.due_date)}</TableCell>
                      <TableCell>
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${INVOICE_STATUS_COLORS[inv.status]}`}>
                          {INVOICE_STATUS_LABELS[inv.status]}
                        </span>
                      </TableCell>
                      <TableCell className="text-right font-medium">
                        {formatCurrency(inv.total_gross)}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </TabsContent>
      </Tabs>

      {/* Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl flex flex-col max-h-[90vh] p-0 gap-0">
          <DialogHeader className="px-6 pt-6 pb-4 border-b shrink-0">
            <DialogTitle>Kunde bearbeiten</DialogTitle>
          </DialogHeader>
          <form
            onSubmit={handleSubmit((data) => updateMutation.mutate(data), (errs) => {
              const fields = Object.keys(errs).join(', ')
              toast({ title: 'Pflichtfelder fehlen', description: fields, variant: 'destructive' })
            })}
            className="flex flex-col flex-1 min-h-0"
          >
            <div className="overflow-y-auto flex-1 px-6 py-5 space-y-5">

              {/* Typ-Auswahl */}
              <div className="space-y-2">
                <Label>Kundentyp</Label>
                <div className="flex gap-2">
                  {(['weg', 'company', 'person'] as const).map((t) => (
                    <label key={t} className={`flex-1 flex items-center justify-center gap-2 border rounded-lg px-3 py-2 cursor-pointer text-sm font-medium transition-colors ${customerType === t ? 'bg-primary text-primary-foreground border-primary' : 'hover:bg-muted'}`}>
                      <input type="radio" value={t} {...register('customer_type')} className="hidden" />
                      {t === 'weg' ? 'WEG' : t === 'company' ? 'Firma' : 'Person'}
                    </label>
                  ))}
                </div>
              </div>

              {/* WEG */}
              {customerType === 'weg' && (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label>WEG-Name *</Label>
                    <Input {...register('company_name')} placeholder="WEG Musterstraße 17" />
                  </div>
                  <div className="space-y-2">
                    <Label>c/o</Label>
                    <Input {...register('address_line2')} placeholder="c/o Demme Immobilien Verwaltung GmbH" />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2 col-span-2">
                      <Label>Straße / Hausnummer</Label>
                      <Input {...register('address_line1')} />
                    </div>
                    <div className="space-y-2">
                      <Label>PLZ</Label>
                      <Input {...register('postal_code')} />
                    </div>
                    <div className="space-y-2">
                      <Label>Ort</Label>
                      <Input {...register('city')} />
                    </div>
                    <div className="space-y-2">
                      <Label>E-Mail</Label>
                      <Input type="email" {...register('email')} />
                    </div>
                    <div className="space-y-2">
                      <Label>Telefon</Label>
                      <Input {...register('phone')} />
                    </div>
                  </div>
                </div>
              )}

              {/* Firma */}
              {customerType === 'company' && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2 col-span-2">
                    <Label>Firmenname *</Label>
                    <Input {...register('company_name')} />
                  </div>
                  <div className="space-y-2">
                    <Label>Anrede</Label>
                    <Input {...register('salutation')} placeholder="Herr / Frau" />
                  </div>
                  <div className="space-y-2">
                    <Label>Vorname</Label>
                    <Input {...register('first_name')} />
                  </div>
                  <div className="space-y-2 col-span-2">
                    <Label>Nachname (Ansprechpartner)</Label>
                    <Input {...register('last_name')} />
                  </div>
                  <div className="space-y-2 col-span-2">
                    <Label>Straße / Hausnummer</Label>
                    <Input {...register('address_line1')} />
                  </div>
                  <div className="space-y-2">
                    <Label>PLZ</Label>
                    <Input {...register('postal_code')} />
                  </div>
                  <div className="space-y-2">
                    <Label>Ort</Label>
                    <Input {...register('city')} />
                  </div>
                  <div className="space-y-2">
                    <Label>E-Mail</Label>
                    <Input type="email" {...register('email')} />
                  </div>
                  <div className="space-y-2">
                    <Label>Telefon</Label>
                    <Input {...register('phone')} />
                  </div>
                  <div className="space-y-2">
                    <Label>Ust-IdNr.</Label>
                    <Input {...register('vat_id')} />
                  </div>
                  <div className="space-y-2">
                    <Label>DATEV-Konto</Label>
                    <Input {...register('datev_account_number')} />
                  </div>
                </div>
              )}

              {/* Person */}
              {customerType === 'person' && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Anrede</Label>
                    <Input {...register('salutation')} placeholder="Herr / Frau" />
                  </div>
                  <div className="space-y-2">
                    <Label>Vorname *</Label>
                    <Input {...register('first_name')} />
                  </div>
                  <div className="space-y-2 col-span-2">
                    <Label>Nachname *</Label>
                    <Input {...register('last_name')} />
                  </div>
                  <div className="space-y-2 col-span-2">
                    <Label>Straße / Hausnummer</Label>
                    <Input {...register('address_line1')} />
                  </div>
                  <div className="space-y-2">
                    <Label>PLZ</Label>
                    <Input {...register('postal_code')} />
                  </div>
                  <div className="space-y-2">
                    <Label>Ort</Label>
                    <Input {...register('city')} />
                  </div>
                  <div className="space-y-2">
                    <Label>E-Mail</Label>
                    <Input type="email" {...register('email')} />
                  </div>
                  <div className="space-y-2">
                    <Label>Telefon</Label>
                    <Input {...register('phone')} />
                  </div>
                </div>
              )}

              {/* Bankdaten */}
              <div className="border-t pt-4 space-y-3">
                <p className="text-sm font-medium text-muted-foreground">Bankverbindung</p>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2 col-span-2">
                    <Label>IBAN</Label>
                    <Input
                      {...register('iban')}
                      onBlur={async (e) => {
                        const val = e.target.value.replace(/\s/g, '').toUpperCase()
                        if (!val || !validateIban(val)) return
                        setBicLoading(true)
                        const bic = await lookupBicFromIban(val)
                        setBicLoading(false)
                        if (bic) setValue('bic', bic)
                      }}
                    />
                    {errors.iban && <p className="text-xs text-red-500">{errors.iban.message}</p>}
                  </div>
                  <div className="space-y-2">
                    <Label>BIC</Label>
                    <div className="relative">
                      <Input {...register('bic')} />
                      {bicLoading && <Loader2 className="absolute right-2 top-2.5 h-4 w-4 animate-spin text-muted-foreground" />}
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label>Bank</Label>
                    <Input {...register('bank_name')} />
                  </div>
                  <div className="space-y-2 col-span-2">
                    <Label>Kontoinhaber</Label>
                    <Input {...register('account_holder')} />
                  </div>
                </div>
              </div>

              {/* Kundennummer + Notizen */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Kundennummer</Label>
                  <Input {...register('customer_number')} readOnly className="bg-muted" />
                </div>
                <div className="space-y-2">
                  <Label>Notizen</Label>
                  <Input {...register('notes')} />
                </div>
              </div>

              {/* Aktiv-Status */}
              <div className="flex items-center gap-2">
                <input type="checkbox" id="is_active" {...register('is_active')} className="h-4 w-4" />
                <Label htmlFor="is_active">Kunde aktiv</Label>
              </div>

            </div>
            <DialogFooter className="px-6 py-4 border-t shrink-0">
              <Button variant="outline" type="button" onClick={() => setDialogOpen(false)}>
                Abbrechen
              </Button>
              <Button type="submit" disabled={updateMutation.isPending}>
                {updateMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Speichern
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
