import { useState, useRef } from 'react'
import { useWatch } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Plus, Search, Upload, Pencil, Trash2, Loader2, AlertCircle, CheckCircle } from 'lucide-react'
import api from '@/lib/api'
import type { Customer, CustomerListResponse, CustomerImportRow } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { toast } from '@/hooks/use-toast'
import { formatDate, validateIban, lookupBicFromIban } from '@/lib/utils'

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

export function CustomerListPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<Customer | null>(null)
  const [importOpen, setImportOpen] = useState(false)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [previewRows, setPreviewRows] = useState<CustomerImportRow[]>([])
  const [previewLoading, setPreviewLoading] = useState(false)
  const [bicLoading, setBicLoading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['customers', search, page],
    queryFn: () =>
      api.get<CustomerListResponse>('/customers', {
        params: { search: search || undefined, page, page_size: 25 },
      }).then((r) => r.data),
  })

  const { register, handleSubmit, reset, control, setValue, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { customer_type: 'weg' },
  })
  const customerType = useWatch({ control, name: 'customer_type' })

  function formatApiError(err: any): string {
    const detail = err?.response?.data?.detail
    if (!detail) return err?.message || 'Unbekannter Fehler'
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((e: any) => e.msg || JSON.stringify(e)).join(' | ')
    return JSON.stringify(detail)
  }

  const createMutation = useMutation({
    mutationFn: (data: FormData) => api.post('/customers', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] })
      setDialogOpen(false)
      toast({ title: 'Kunde erstellt' })
    },
    onError: (err: any) => {
      toast({ title: 'Fehler beim Speichern', description: formatApiError(err), variant: 'destructive' })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: FormData }) =>
      api.put(`/customers/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] })
      setDialogOpen(false)
      toast({ title: 'Kunde aktualisiert' })
    },
    onError: (err: any) => {
      toast({ title: 'Fehler beim Speichern', description: formatApiError(err), variant: 'destructive' })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/customers/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] })
      toast({ title: 'Kunde gelöscht' })
    },
  })

  const confirmImportMutation = useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      return api.post('/customers/import/confirm', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    },
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['customers'] })
      setImportOpen(false)
      setPreviewRows([])
      setImportFile(null)
      toast({ title: `${res.data.length} Kunden importiert` })
    },
    onError: (err: any) => {
      toast({ title: 'Fehler', description: err?.response?.data?.detail, variant: 'destructive' })
    },
  })

  async function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setImportFile(file)
    setPreviewLoading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await api.post('/customers/import/preview', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setPreviewRows(res.data)
    } catch {
      toast({ title: 'Fehler beim Lesen der CSV-Datei', variant: 'destructive' })
    } finally {
      setPreviewLoading(false)
    }
  }

  function openCreate() {
    setEditing(null)
    reset({ customer_type: 'weg', country_code: 'DE', is_active: true })
    setDialogOpen(true)
  }

  function openEdit(c: Customer) {
    setEditing(c)
    reset({
      customer_number: c.customer_number,
      customer_type: c.customer_type || 'weg',
      company_name: c.company_name || '',
      salutation: c.salutation || '',
      first_name: c.first_name || '',
      last_name: c.last_name || '',
      address_line1: c.address_line1 || '',
      address_line2: c.address_line2 || '',
      postal_code: c.postal_code || '',
      city: c.city || '',
      country_code: c.country_code,
      email: c.email || '',
      phone: c.phone || '',
      vat_id: c.vat_id || '',
      iban: c.iban || '',
      bic: c.bic || '',
      bank_name: c.bank_name || '',
      account_holder: c.account_holder || '',
      datev_account_number: c.datev_account_number || '',
      notes: c.notes || '',
      is_active: c.is_active,
    })
    setDialogOpen(true)
  }

  function onSubmit(data: FormData) {
    if (editing) {
      updateMutation.mutate({ id: editing.id, data })
    } else {
      createMutation.mutate(data)
    }
  }

  const customers = data?.items || []
  const total = data?.total || 0
  const totalPages = Math.ceil(total / 25)

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Kunden</h1>
          <p className="text-sm text-slate-500 mt-1">{total} Kunden insgesamt</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setImportOpen(true)}>
            <Upload className="h-4 w-4 mr-2" /> CSV importieren
          </Button>
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4 mr-2" /> Neuer Kunde
          </Button>
        </div>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder="Suche nach Name, Nummer, E-Mail..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1) }}
        />
      </div>

      {/* Table */}
      <div className="border rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Kundennummer</TableHead>
              <TableHead>Name / Firma</TableHead>
              <TableHead>Typ</TableHead>
              <TableHead>Ort</TableHead>
              <TableHead>E-Mail</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-24">Aktionen</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-12">
                  <Loader2 className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
                </TableCell>
              </TableRow>
            ) : customers.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-12">
                  Keine Kunden gefunden
                </TableCell>
              </TableRow>
            ) : (
              customers.map((c) => (
                <TableRow
                  key={c.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/customers/${c.id}`)}
                >
                  <TableCell className="font-mono text-sm">{c.customer_number}</TableCell>
                  <TableCell>
                    <div className="font-medium">
                      {c.company_name || `${c.first_name || ''} ${c.last_name || ''}`.trim() || '–'}
                    </div>
                    {c.address_line2 && (
                      <div className="text-xs text-muted-foreground">{c.address_line2}</div>
                    )}
                    {c.customer_type !== 'weg' && c.company_name && (c.first_name || c.last_name) && (
                      <div className="text-xs text-muted-foreground">
                        {`${c.first_name || ''} ${c.last_name || ''}`.trim()}
                      </div>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-xs">
                      {c.customer_type === 'weg' ? 'WEG' : c.customer_type === 'company' ? 'Firma' : 'Person'}
                    </Badge>
                  </TableCell>
                  <TableCell>{c.postal_code && c.city ? `${c.postal_code} ${c.city}` : c.city || '–'}</TableCell>
                  <TableCell className="text-sm">{c.email || '–'}</TableCell>
                  <TableCell>
                    <Badge variant={c.is_active ? 'default' : 'secondary'}>
                      {c.is_active ? 'Aktiv' : 'Inaktiv'}
                    </Badge>
                  </TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="icon" onClick={() => openEdit(c)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => {
                          if (confirm(`Kunde "${c.customer_number}" löschen?`)) {
                            deleteMutation.mutate(c.id)
                          }
                        }}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center gap-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
            Zurück
          </Button>
          <span className="py-2 px-3 text-sm">Seite {page} von {totalPages}</span>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
            Weiter
          </Button>
        </div>
      )}

      {/* Import Dialog */}
      <Dialog open={importOpen} onOpenChange={(open) => { setImportOpen(open); if (!open) setPreviewRows([]) }}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Kunden aus CSV importieren</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="text-sm text-muted-foreground">
              Pflichtfeld: <span className="font-mono">customer_number</span>. Optional: company_name, first_name, last_name, address_line1, postal_code, city, email, phone, iban, bic, vat_id, datev_account_number, notes, …
            </div>
            <div className="flex items-center gap-3">
              <input
                ref={fileRef}
                type="file"
                accept=".csv"
                className="hidden"
                onChange={handleFileSelect}
              />
              <Button variant="outline" onClick={() => fileRef.current?.click()}>
                <Upload className="h-4 w-4 mr-2" /> CSV-Datei wählen
              </Button>
              {importFile && <span className="text-sm text-muted-foreground">{importFile.name}</span>}
            </div>

            {previewLoading && (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Vorschau wird geladen...
              </div>
            )}

            {previewRows.length > 0 && (
              <div className="border rounded-lg overflow-auto max-h-80">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-10">Zeile</TableHead>
                      <TableHead>Kundennr.</TableHead>
                      <TableHead>Firma / Name</TableHead>
                      <TableHead>Ort</TableHead>
                      <TableHead>E-Mail</TableHead>
                      <TableHead>Gültig</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {previewRows.map((row) => (
                      <TableRow key={row.row_number} className={row.is_valid ? '' : 'bg-red-50'}>
                        <TableCell className="text-xs text-muted-foreground">{row.row_number}</TableCell>
                        <TableCell className="font-mono text-sm">{row.customer_number}</TableCell>
                        <TableCell>
                          {row.company_name || `${row.first_name || ''} ${row.last_name || ''}`.trim() || '–'}
                        </TableCell>
                        <TableCell>{row.postal_code && row.city ? `${row.postal_code} ${row.city}` : row.city || '–'}</TableCell>
                        <TableCell className="text-sm">{row.email || '–'}</TableCell>
                        <TableCell>
                          {row.is_valid ? (
                            <CheckCircle className="h-4 w-4 text-green-500" />
                          ) : (
                            <div className="flex items-center gap-1 text-red-500">
                              <AlertCircle className="h-4 w-4" />
                              <span className="text-xs">{row.errors.join(', ')}</span>
                            </div>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setImportOpen(false); setPreviewRows([]) }}>
              Abbrechen
            </Button>
            <Button
              disabled={!importFile || previewRows.filter(r => r.is_valid).length === 0 || confirmImportMutation.isPending}
              onClick={() => importFile && confirmImportMutation.mutate(importFile)}
            >
              {confirmImportMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {previewRows.filter(r => r.is_valid).length} Kunden importieren
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl flex flex-col max-h-[90vh] p-0 gap-0">
          <DialogHeader className="px-6 pt-6 pb-4 border-b shrink-0">
            <DialogTitle>{editing ? 'Kunde bearbeiten' : 'Neuer Kunde'}</DialogTitle>
          </DialogHeader>
          <form
              onSubmit={handleSubmit(onSubmit, (errs) => {
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
                      <Input {...register('address_line1')} placeholder="Coventrystraße 32" />
                    </div>
                    <div className="space-y-2">
                      <Label>PLZ</Label>
                      <Input {...register('postal_code')} placeholder="65934" />
                    </div>
                    <div className="space-y-2">
                      <Label>Ort</Label>
                      <Input {...register('city')} placeholder="Frankfurt am Main" />
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

              {/* Bankdaten (alle Typen) */}
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

              {/* Notizen + Kundennummer (beim Bearbeiten) */}
              <div className="grid grid-cols-2 gap-4">
                {editing && (
                  <div className="space-y-2">
                    <Label>Kundennummer</Label>
                    <Input {...register('customer_number')} />
                  </div>
                )}
                <div className={`space-y-2 ${editing ? '' : 'col-span-2'}`}>
                  <Label>Notizen</Label>
                  <Input {...register('notes')} />
                </div>
              </div>

            </div>
            <DialogFooter className="px-6 py-4 border-t shrink-0">
              <Button variant="outline" type="button" onClick={() => setDialogOpen(false)}>
                Abbrechen
              </Button>
              <Button type="submit" disabled={createMutation.isPending || updateMutation.isPending}>
                {(createMutation.isPending || updateMutation.isPending) && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                {editing ? 'Speichern' : 'Erstellen'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
