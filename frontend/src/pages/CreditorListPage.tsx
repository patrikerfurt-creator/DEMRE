import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Plus, Search, Pencil, Trash2, Loader2 } from 'lucide-react'
import api from '@/lib/api'
import type { Creditor, CreditorListResponse } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { toast } from '@/hooks/use-toast'

const schema = z.object({
  company_name: z.string().optional(),
  first_name: z.string().optional(),
  last_name: z.string().optional(),
  address_line1: z.string().optional(),
  postal_code: z.string().optional(),
  city: z.string().optional(),
  country_code: z.string().default('DE'),
  email: z.string().optional(),
  phone: z.string().optional(),
  iban: z.string().optional(),
  bic: z.string().optional(),
  bank_name: z.string().optional(),
  account_holder: z.string().optional(),
  vat_id: z.string().optional(),
  tax_number: z.string().optional(),
  datev_account_number: z.string().optional(),
  payment_terms_days: z.coerce.number().default(30),
  notes: z.string().optional(),
  is_active: z.boolean().default(true),
})
type FormData = z.infer<typeof schema>

export function CreditorListPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<Creditor | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['creditors', search, page],
    queryFn: () =>
      api.get<CreditorListResponse>('/creditors', {
        params: { search: search || undefined, page, page_size: 25 },
      }).then((r) => r.data),
  })

  const { register, handleSubmit, reset, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  })

  const createMutation = useMutation({
    mutationFn: (data: FormData) => api.post('/creditors', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['creditors'] })
      setDialogOpen(false)
      toast({ title: 'Kreditor angelegt' })
    },
    onError: (err: any) => toast({ title: 'Fehler', description: err?.response?.data?.detail, variant: 'destructive' }),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: FormData }) => api.put(`/creditors/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['creditors'] })
      setDialogOpen(false)
      toast({ title: 'Kreditor aktualisiert' })
    },
    onError: (err: any) => toast({ title: 'Fehler', description: err?.response?.data?.detail, variant: 'destructive' }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/creditors/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['creditors'] })
      toast({ title: 'Kreditor gelöscht' })
    },
    onError: (err: any) => toast({ title: 'Fehler', description: err?.response?.data?.detail, variant: 'destructive' }),
  })

  function openCreate() {
    setEditing(null)
    reset({ country_code: 'DE', payment_terms_days: 30, is_active: true })
    setDialogOpen(true)
  }

  function openEdit(c: Creditor) {
    setEditing(c)
    reset({
      company_name: c.company_name || '',
      first_name: c.first_name || '',
      last_name: c.last_name || '',
      address_line1: c.address_line1 || '',
      postal_code: c.postal_code || '',
      city: c.city || '',
      country_code: c.country_code,
      email: c.email || '',
      phone: c.phone || '',
      iban: c.iban || '',
      bic: c.bic || '',
      bank_name: c.bank_name || '',
      account_holder: c.account_holder || '',
      vat_id: c.vat_id || '',
      tax_number: c.tax_number || '',
      datev_account_number: c.datev_account_number || '',
      payment_terms_days: c.payment_terms_days,
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

  const items = data?.items ?? []
  const total = data?.total ?? 0
  const totalPages = Math.ceil(total / 25)

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Kreditoren</h1>
          <p className="text-sm text-slate-500 mt-1">{total} Kreditoren</p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4 mr-2" /> Neuer Kreditor
        </Button>
      </div>

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder="Suche nach Nummer, Name, Ort..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1) }}
        />
      </div>

      <div className="border rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Kred.-Nr.</TableHead>
              <TableHead>Name / Firma</TableHead>
              <TableHead>Ort</TableHead>
              <TableHead>E-Mail</TableHead>
              <TableHead>IBAN</TableHead>
              <TableHead>Zahlungsziel</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-24">Aktionen</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center py-12">
                  <Loader2 className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
                </TableCell>
              </TableRow>
            ) : items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center text-muted-foreground py-12">
                  Keine Kreditoren gefunden
                </TableCell>
              </TableRow>
            ) : (
              items.map((c) => (
                <TableRow key={c.id} className="cursor-pointer hover:bg-slate-50" onClick={() => navigate(`/creditors/${c.id}`)}>
                  <TableCell className="font-mono text-sm">{c.creditor_number}</TableCell>
                  <TableCell>
                    <div className="font-medium">
                      {c.company_name || [c.first_name, c.last_name].filter(Boolean).join(' ') || '–'}
                    </div>
                  </TableCell>
                  <TableCell>{[c.postal_code, c.city].filter(Boolean).join(' ') || '–'}</TableCell>
                  <TableCell className="text-sm">{c.email || '–'}</TableCell>
                  <TableCell className="font-mono text-xs">{c.iban || '–'}</TableCell>
                  <TableCell>{c.payment_terms_days} Tage</TableCell>
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
                          if (confirm(`Kreditor "${c.creditor_number}" löschen?`)) {
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

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>{total} Einträge</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Zurück</Button>
            <span className="px-2 py-1">Seite {page} / {totalPages}</span>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Weiter</Button>
          </div>
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editing ? 'Kreditor bearbeiten' : 'Neuer Kreditor'}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2 space-y-2">
                <Label>Firma</Label>
                <Input {...register('company_name')} placeholder="Firmenname" />
              </div>
              <div className="space-y-2">
                <Label>Vorname</Label>
                <Input {...register('first_name')} />
              </div>
              <div className="space-y-2">
                <Label>Nachname</Label>
                <Input {...register('last_name')} />
              </div>
              <div className="col-span-2 space-y-2">
                <Label>Straße</Label>
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

            <div className="border-t pt-4">
              <div className="text-sm font-semibold text-slate-700 mb-3">Bankverbindung</div>
              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2 space-y-2">
                  <Label>IBAN</Label>
                  <Input {...register('iban')} placeholder="DE..." />
                </div>
                <div className="space-y-2">
                  <Label>BIC</Label>
                  <Input {...register('bic')} />
                </div>
                <div className="space-y-2">
                  <Label>Bank</Label>
                  <Input {...register('bank_name')} />
                </div>
                <div className="col-span-2 space-y-2">
                  <Label>Kontoinhaber</Label>
                  <Input {...register('account_holder')} />
                </div>
              </div>
            </div>

            <div className="border-t pt-4">
              <div className="text-sm font-semibold text-slate-700 mb-3">Steuer & Sonstiges</div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>USt-IdNr.</Label>
                  <Input {...register('vat_id')} />
                </div>
                <div className="space-y-2">
                  <Label>Steuernummer</Label>
                  <Input {...register('tax_number')} />
                </div>
                <div className="space-y-2">
                  <Label>DATEV-Konto</Label>
                  <Input {...register('datev_account_number')} />
                </div>
                <div className="space-y-2">
                  <Label>Zahlungsziel (Tage)</Label>
                  <Input type="number" {...register('payment_terms_days')} />
                </div>
                <div className="col-span-2 space-y-2">
                  <Label>Notizen</Label>
                  <Input {...register('notes')} />
                </div>
              </div>
            </div>

            <DialogFooter>
              <Button variant="outline" type="button" onClick={() => setDialogOpen(false)}>Abbrechen</Button>
              <Button type="submit" disabled={createMutation.isPending || updateMutation.isPending}>
                {(createMutation.isPending || updateMutation.isPending) && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {editing ? 'Speichern' : 'Anlegen'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
