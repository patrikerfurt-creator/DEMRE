import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Plus, Upload, Pencil, CheckCircle, XCircle, Loader2, Eye, Trash2, RefreshCw, CreditCard, Banknote } from 'lucide-react'
import api, { openDocument } from '@/lib/api'
import type { IncomingInvoice, IncomingInvoiceListResponse, Creditor, CreditorListResponse, IncomingInvoiceStatus } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { toast } from '@/hooks/use-toast'
import { formatCurrency } from '@/lib/utils'

const STATUS_LABELS: Record<IncomingInvoiceStatus, string> = {
  open: 'Offen',
  approved: 'Genehmigt',
  scheduled: 'Geplant',
  paid: 'Bezahlt',
  rejected: 'Abgelehnt',
  cancelled: 'Storniert',
}

const STATUS_VARIANTS: Record<IncomingInvoiceStatus, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  open: 'outline',
  approved: 'default',
  scheduled: 'secondary',
  paid: 'default',
  rejected: 'destructive',
  cancelled: 'secondary',
}

const schema = z.object({
  creditor_id: z.string().min(1, 'Kreditor ist Pflichtfeld'),
  external_invoice_number: z.string().optional(),
  invoice_date: z.string().min(1),
  receipt_date: z.string().optional(),
  due_date: z.string().optional(),
  total_net: z.coerce.number().default(0),
  total_vat: z.coerce.number().default(0),
  total_gross: z.coerce.number().default(0),
  currency: z.string().default('EUR'),
  description: z.string().optional(),
  cost_account: z.string().optional(),
  notes: z.string().optional(),
  is_direct_debit: z.boolean().default(false),
})
type FormData = z.infer<typeof schema>

interface PendingFile {
  filename: string
  size: number
  created_at: string
  extracted?: Record<string, any>
  extraction_error?: string
  matched_creditor?: { id: string; creditor_number: string; company_name: string } | null
  is_direct_debit?: boolean
}

export function IncomingInvoiceListPage() {
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState('')
  const [page, setPage] = useState(1)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<IncomingInvoice | null>(null)
  const [uploadInvoice, setUploadInvoice] = useState<IncomingInvoice | null>(null)
  const [pendingSourceFile, setPendingSourceFile] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['incoming-invoices', statusFilter, page],
    queryFn: () =>
      api.get<IncomingInvoiceListResponse>('/incoming-invoices', {
        params: { status: statusFilter || undefined, page, page_size: 25 },
      }).then((r) => r.data),
  })

  const { data: creditorsData } = useQuery({
    queryKey: ['creditors-all'],
    queryFn: () =>
      api.get<CreditorListResponse>('/creditors', { params: { page_size: 100, is_active: true } }).then((r) => r.data),
  })
  const creditors = creditorsData?.items ?? []

  const { data: pendingData, refetch: refetchPending } = useQuery({
    queryKey: ['incoming-invoices-pending'],
    queryFn: () => api.get<{ files: PendingFile[] }>('/incoming-invoices/pending').then((r) => r.data),
  })
  const pendingFiles = pendingData?.files ?? []

  const { register, handleSubmit, reset, setValue, watch } = useForm<FormData>({
    resolver: zodResolver(schema),
  })
  const isDirectDebit = watch('is_direct_debit', false)

  const createMutation = useMutation({
    mutationFn: (data: FormData) => api.post('/incoming-invoices', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incoming-invoices'] })
      setDialogOpen(false)
      toast({ title: 'Eingangsrechnung angelegt' })
    },
    onError: (err: any) => toast({ title: 'Fehler', description: err?.response?.data?.detail, variant: 'destructive' }),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: FormData }) => api.put(`/incoming-invoices/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incoming-invoices'] })
      setDialogOpen(false)
      toast({ title: 'Eingangsrechnung aktualisiert' })
    },
    onError: (err: any) => toast({ title: 'Fehler', description: err?.response?.data?.detail, variant: 'destructive' }),
  })

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.put(`/incoming-invoices/${id}/status`, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incoming-invoices'] })
      toast({ title: 'Status aktualisiert' })
    },
    onError: (err: any) => toast({ title: 'Fehler', description: err?.response?.data?.detail, variant: 'destructive' }),
  })

  const uploadMutation = useMutation({
    mutationFn: ({ id, file }: { id: string; file: File }) => {
      const formData = new FormData()
      formData.append('file', file)
      return api.post(`/incoming-invoices/${id}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incoming-invoices'] })
      setUploadInvoice(null)
      toast({ title: 'Dokument hochgeladen' })
    },
    onError: (err: any) => toast({ title: 'Fehler', description: err?.response?.data?.detail, variant: 'destructive' }),
  })

  const deletePendingMutation = useMutation({
    mutationFn: (filename: string) => api.delete(`/incoming-invoices/pending/${encodeURIComponent(filename)}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incoming-invoices-pending'] })
      toast({ title: 'Datei gelöscht' })
    },
    onError: () => toast({ title: 'Fehler beim Löschen', variant: 'destructive' }),
  })

  const extractPendingMutation = useMutation({
    mutationFn: (filename: string) =>
      api.post(`/incoming-invoices/pending/${encodeURIComponent(filename)}/extract`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incoming-invoices-pending'] })
      toast({ title: 'Extraktion gestartet' })
    },
    onError: () => toast({ title: 'Fehler bei der Extraktion', variant: 'destructive' }),
  })

  function openCreate() {
    setEditing(null)
    setPendingSourceFile(null)
    reset({ currency: 'EUR', invoice_date: new Date().toISOString().slice(0, 10), is_direct_debit: false })
    setDialogOpen(true)
  }

  function openEdit(inv: IncomingInvoice) {
    setEditing(inv)
    setPendingSourceFile(null)
    reset({
      creditor_id: inv.creditor_id,
      external_invoice_number: inv.external_invoice_number || '',
      invoice_date: inv.invoice_date,
      receipt_date: inv.receipt_date || '',
      due_date: inv.due_date || '',
      total_net: parseFloat(inv.total_net),
      total_vat: parseFloat(inv.total_vat),
      total_gross: parseFloat(inv.total_gross),
      currency: inv.currency,
      description: inv.description || '',
      cost_account: inv.cost_account || '',
      notes: inv.notes || '',
      is_direct_debit: inv.is_direct_debit,
    })
    setDialogOpen(true)
  }

  function openFromPending(pf: PendingFile) {
    setEditing(null)
    setPendingSourceFile(pf.filename)
    const d = pf.extracted ?? {}
    reset({
      creditor_id: pf.matched_creditor?.id ?? '',
      external_invoice_number: d.external_invoice_number ?? '',
      invoice_date: d.invoice_date ?? new Date().toISOString().slice(0, 10),
      receipt_date: new Date().toISOString().slice(0, 10),
      due_date: d.due_date ?? '',
      total_net: parseFloat(d.total_net) || 0,
      total_vat: parseFloat(d.total_vat) || 0,
      total_gross: parseFloat(d.total_gross) || 0,
      currency: d.currency ?? 'EUR',
      description: d.description ?? '',
      cost_account: '',
      notes: '',
      is_direct_debit: pf.is_direct_debit ?? false,
    })
    setDialogOpen(true)
  }

  function onSubmit(data: FormData) {
    if (editing) {
      updateMutation.mutate({ id: editing.id, data })
    } else {
      const payload: any = { ...data }
      if (pendingSourceFile) payload.source_pending_file = pendingSourceFile
      createMutation.mutate(payload)
    }
  }

  function creditorName(c?: { company_name?: string; first_name?: string; last_name?: string }) {
    if (!c) return '–'
    return c.company_name || [c.first_name, c.last_name].filter(Boolean).join(' ') || '–'
  }

  const items = data?.items ?? []
  const total = data?.total ?? 0
  const totalPages = Math.ceil(total / 25)
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Eingangsrechnungen</h1>
          <p className="text-sm text-slate-500 mt-1">{total} Einträge</p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4 mr-2" /> Neue Eingangsrechnung
        </Button>
      </div>

      {/* Pending-Panel: Dateien aus dem Eingangsordner */}
      {pendingFiles.length > 0 && (
        <div className="border border-amber-200 bg-amber-50 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="font-semibold text-amber-900 text-sm">
              Eingang Ordner – {pendingFiles.length} Datei(en) warten auf Übernahme
            </div>
            <Button variant="ghost" size="sm" onClick={() => refetchPending()}>
              <RefreshCw className="h-3 w-3 mr-1" /> Aktualisieren
            </Button>
          </div>
          <div className="space-y-2">
            {pendingFiles.map((pf) => (
              <div key={pf.filename} className="flex items-center gap-3 bg-white rounded border px-3 py-2 text-sm">
                <div className="flex-1 min-w-0">
                  <div className="font-medium truncate">{pf.filename}</div>
                  {pf.extraction_error ? (
                    <div className="text-xs text-red-600">Fehler: {pf.extraction_error}</div>
                  ) : pf.extracted ? (
                    <div className="text-xs text-slate-500 flex gap-3 flex-wrap">
                      {pf.extracted.creditor_name && <span>Kreditor: <strong>{pf.extracted.creditor_name}</strong></span>}
                      {pf.extracted.total_gross && <span>Betrag: <strong>{formatCurrency(pf.extracted.total_gross)}</strong></span>}
                      {pf.extracted.invoice_date && <span>Datum: {pf.extracted.invoice_date}</span>}
                      {pf.is_direct_debit && (
                        <span className="inline-flex items-center gap-1 text-blue-700">
                          <CreditCard className="h-3 w-3" /> Lastschrift erkannt
                        </span>
                      )}
                      {pf.matched_creditor && (
                        <span className="text-green-700">Kreditor gefunden: {pf.matched_creditor.company_name}</span>
                      )}
                    </div>
                  ) : (
                    <div className="text-xs text-slate-400">Extraktion ausstehend…</div>
                  )}
                </div>
                <div className="flex gap-1 shrink-0">
                  <Button
                    variant="ghost"
                    size="icon"
                    title="Vorschau"
                    onClick={() => openDocument(`/incoming-invoices/pending/${encodeURIComponent(pf.filename)}/download`)}
                  >
                    <Eye className="h-4 w-4" />
                  </Button>
                  {pf.extraction_error && (
                    <Button
                      variant="ghost"
                      size="icon"
                      title="Erneut extrahieren"
                      onClick={() => extractPendingMutation.mutate(pf.filename)}
                    >
                      <RefreshCw className="h-4 w-4" />
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    title="Als Eingangsrechnung übernehmen"
                    onClick={() => openFromPending(pf)}
                    className="text-green-700"
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    title="Löschen"
                    onClick={() => deletePendingMutation.mutate(pf.filename)}
                    className="text-red-600"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex gap-2 items-center">
        <select
          className="border rounded-md px-3 py-2 text-sm bg-background"
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
        >
          <option value="">Alle Status</option>
          {Object.entries(STATUS_LABELS).map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
      </div>

      <div className="border rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Belegnr.</TableHead>
              <TableHead>Kreditor</TableHead>
              <TableHead>Rechnungsdatum</TableHead>
              <TableHead>Fälligkeit</TableHead>
              <TableHead className="text-right">Brutto</TableHead>
              <TableHead>Zahlung</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Dokument</TableHead>
              <TableHead className="w-32">Aktionen</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={9} className="text-center py-12">
                  <Loader2 className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
                </TableCell>
              </TableRow>
            ) : items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} className="text-center text-muted-foreground py-12">
                  Keine Eingangsrechnungen gefunden
                </TableCell>
              </TableRow>
            ) : (
              items.map((inv) => (
                <TableRow key={inv.id}>
                  <TableCell className="font-mono text-sm">
                    <div>{inv.document_number}</div>
                    {inv.external_invoice_number && (
                      <div className="text-xs text-muted-foreground">{inv.external_invoice_number}</div>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="text-sm font-medium">{creditorName(inv.creditor)}</div>
                    {inv.creditor && <div className="text-xs text-muted-foreground">{inv.creditor.creditor_number}</div>}
                  </TableCell>
                  <TableCell className="text-sm">{inv.invoice_date}</TableCell>
                  <TableCell className="text-sm">{inv.due_date || '–'}</TableCell>
                  <TableCell className="text-right font-medium">{formatCurrency(inv.total_gross)}</TableCell>
                  <TableCell>
                    {inv.is_direct_debit ? (
                      <span className="inline-flex items-center gap-1 text-xs text-blue-700 font-medium">
                        <CreditCard className="h-3 w-3" /> Lastschrift
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                        <Banknote className="h-3 w-3" /> Überweisung
                      </span>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANTS[inv.status]}>
                      {STATUS_LABELS[inv.status]}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {inv.document_path ? (
                      <button
                        onClick={() => openDocument(`/incoming-invoices/${inv.id}/document`)}
                        className="text-blue-600 hover:underline text-xs"
                      >
                        Anzeigen
                      </button>
                    ) : (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-xs h-7"
                        onClick={() => { setUploadInvoice(inv); fileRef.current?.click() }}
                      >
                        <Upload className="h-3 w-3 mr-1" /> Hochladen
                      </Button>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="icon" onClick={() => openEdit(inv)} title="Bearbeiten">
                        <Pencil className="h-4 w-4" />
                      </Button>
                      {inv.status === 'open' && (
                        <Button
                          variant="ghost"
                          size="icon"
                          title="Genehmigen"
                          onClick={() => statusMutation.mutate({ id: inv.id, status: 'approved' })}
                        >
                          <CheckCircle className="h-4 w-4 text-green-600" />
                        </Button>
                      )}
                      {(inv.status === 'open' || inv.status === 'approved') && (
                        <Button
                          variant="ghost"
                          size="icon"
                          title="Ablehnen"
                          onClick={() => statusMutation.mutate({ id: inv.id, status: 'rejected' })}
                        >
                          <XCircle className="h-4 w-4 text-red-600" />
                        </Button>
                      )}
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

      {/* Hidden file input for upload */}
      <input
        ref={fileRef}
        type="file"
        accept=".pdf,.jpg,.jpeg,.png"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file && uploadInvoice) {
            uploadMutation.mutate({ id: uploadInvoice.id, file })
          }
          e.target.value = ''
        }}
      />

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] flex flex-col">
          <DialogHeader className="shrink-0">
            <DialogTitle>
              {editing ? 'Eingangsrechnung bearbeiten' : pendingSourceFile ? 'Rechnung aus Eingangsordner übernehmen' : 'Neue Eingangsrechnung'}
            </DialogTitle>
            {pendingSourceFile && (
              <p className="text-xs text-muted-foreground mt-1">Datei: {pendingSourceFile}</p>
            )}
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col flex-1 overflow-hidden">
            <div className="flex-1 overflow-y-auto pr-1">
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2 space-y-2">
                <Label>Kreditor *</Label>
                <select
                  className="w-full border rounded-md px-3 py-2 text-sm bg-background"
                  {...register('creditor_id')}
                >
                  <option value="">Bitte wählen...</option>
                  {creditors.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.creditor_number} – {c.company_name || [c.first_name, c.last_name].filter(Boolean).join(' ')}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label>Ext. Rechnungsnr.</Label>
                <Input {...register('external_invoice_number')} placeholder="Rechnungsnr. des Lieferanten" />
              </div>
              <div className="space-y-2">
                <Label>Buchungskonto</Label>
                <Input {...register('cost_account')} placeholder="z.B. 4000" />
              </div>
              <div className="space-y-2">
                <Label>Rechnungsdatum *</Label>
                <Input type="date" {...register('invoice_date')} />
              </div>
              <div className="space-y-2">
                <Label>Eingangsdatum</Label>
                <Input type="date" {...register('receipt_date')} />
              </div>
              <div className="space-y-2">
                <Label>Fälligkeitsdatum</Label>
                <Input type="date" {...register('due_date')} />
              </div>
              <div className="space-y-2">
                <Label>Währung</Label>
                <Input {...register('currency')} defaultValue="EUR" />
              </div>
              <div className="space-y-2">
                <Label>Betrag netto</Label>
                <Input type="number" step="0.01" {...register('total_net')} />
              </div>
              <div className="space-y-2">
                <Label>MwSt.-Betrag</Label>
                <Input type="number" step="0.01" {...register('total_vat')} />
              </div>
              <div className="col-span-2 space-y-2">
                <Label>Brutto-Betrag</Label>
                <Input type="number" step="0.01" {...register('total_gross')} />
              </div>
              <div className="col-span-2 space-y-2">
                <Label>Beschreibung / Verwendungszweck</Label>
                <Input {...register('description')} />
              </div>
              <div className="col-span-2 flex items-start gap-3 rounded-md border px-3 py-2 bg-slate-50">
                <input
                  id="is_direct_debit"
                  type="checkbox"
                  className="mt-1 h-4 w-4 cursor-pointer"
                  checked={isDirectDebit}
                  onChange={(e) => setValue('is_direct_debit', e.target.checked)}
                />
                <div>
                  <label htmlFor="is_direct_debit" className="text-sm font-medium cursor-pointer flex items-center gap-2">
                    <CreditCard className="h-4 w-4 text-blue-600" /> SEPA-Lastschrift (wird abgebucht)
                  </label>
                  <p className="text-xs text-muted-foreground">Aktivieren wenn der Betrag per Lastschrift eingezogen wird — nicht in SEPA-Überweisung aufnehmen</p>
                </div>
              </div>
              <div className="col-span-2 space-y-2">
                <Label>Notizen</Label>
                <Input {...register('notes')} />
              </div>
            </div>
            </div>
            <DialogFooter className="shrink-0 pt-4">
              <Button variant="outline" type="button" onClick={() => setDialogOpen(false)}>Abbrechen</Button>
              <Button type="submit" disabled={createMutation.isPending || updateMutation.isPending}>
                {(createMutation.isPending || updateMutation.isPending) && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {editing ? 'Speichern' : pendingSourceFile ? 'Übernehmen' : 'Anlegen'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
