import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Plus, Upload, Pencil, CheckCircle, XCircle, Loader2, Eye, Trash2, RefreshCw, CreditCard, RotateCcw, ShieldCheck, History } from 'lucide-react'
import api, { openDocument } from '@/lib/api'
import type { ExpenseReceipt, ExpenseReceiptListResponse, ExpenseReceiptStatus, StatusChangeLog, User } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { toast } from '@/hooks/use-toast'
import { formatCurrency } from '@/lib/utils'
import { useAuthStore } from '@/store/authStore'

interface PendingReceipt {
  filename: string
  size: number
  created_at: string
  extracted?: {
    merchant?: string
    receipt_date?: string
    amount_gross?: string | number
    vat_amount?: string | number
    amount_net?: string | number
    vat_rate?: string | number
    currency?: string
    category?: string
    description?: string
    payment_method?: string
  }
  extraction_error?: string
}

const STATUS_LABELS: Record<ExpenseReceiptStatus, string> = {
  submitted: 'Eingereicht',
  approved: 'Genehmigt',
  paid: 'Bezahlt',
  rejected: 'Abgelehnt',
}

const STATUS_VARIANTS: Record<ExpenseReceiptStatus, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  submitted: 'outline',
  approved: 'default',
  paid: 'default',
  rejected: 'destructive',
}

const CATEGORIES = ['Büromaterial', 'Reisekosten', 'Bewirtung', 'Porto', 'Telefon', 'Software', 'Sonstiges']

const schema = z.object({
  receipt_date: z.string().min(1),
  merchant: z.string().optional(),
  amount_gross: z.coerce.number().min(0),
  vat_amount: z.coerce.number().min(0).default(0),
  amount_net: z.coerce.number().min(0).default(0),
  vat_rate: z.coerce.number().default(19),
  category: z.string().optional(),
  description: z.string().optional(),
  payment_method: z.string().optional(),
  reimbursement_iban: z.string().optional(),
  reimbursement_account_holder: z.string().optional(),
  notes: z.string().optional(),
  submitted_by_id: z.string().optional(),
})
type FormData = z.infer<typeof schema>

function ReceiptTable({
  items,
  isLoading,
  isAdmin,
  onEdit,
  onApprove,
  onReject,
  onUpload,
  onReset,
  onStatusOverride,
  onShowHistory,
}: {
  items: ExpenseReceipt[]
  isLoading: boolean
  isAdmin: boolean
  onEdit: (r: ExpenseReceipt) => void
  onApprove: (r: ExpenseReceipt) => void
  onReject: (r: ExpenseReceipt) => void
  onUpload: (r: ExpenseReceipt) => void
  onReset: (r: ExpenseReceipt) => void
  onStatusOverride?: (r: ExpenseReceipt) => void
  onShowHistory?: (r: ExpenseReceipt) => void
}) {
  return (
    <div className="border rounded-lg">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Belegnr.</TableHead>
            {isAdmin && <TableHead>Eingereicht von</TableHead>}
            <TableHead>Datum</TableHead>
            <TableHead>Händler</TableHead>
            <TableHead>Kategorie</TableHead>
            <TableHead className="text-right">Brutto</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Beleg</TableHead>
            <TableHead className="w-32">Aktionen</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            <TableRow>
              <TableCell colSpan={isAdmin ? 9 : 8} className="text-center py-12">
                <Loader2 className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
              </TableCell>
            </TableRow>
          ) : items.length === 0 ? (
            <TableRow>
              <TableCell colSpan={isAdmin ? 9 : 8} className="text-center text-muted-foreground py-12">
                Keine Belege gefunden
              </TableCell>
            </TableRow>
          ) : (
            items.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="font-mono text-sm">{r.receipt_number}</TableCell>
                {isAdmin && (
                  <TableCell className="text-sm">
                    {r.submitter?.full_name || '–'}
                  </TableCell>
                )}
                <TableCell className="text-sm">{r.receipt_date}</TableCell>
                <TableCell className="text-sm">{r.merchant || '–'}</TableCell>
                <TableCell className="text-sm">{r.category || '–'}</TableCell>
                <TableCell className="text-right font-medium">
                  <div className="flex items-center justify-end gap-1.5">
                    {formatCurrency(r.amount_gross)}
                    {r.payment_method === 'Kreditkarte' && (
                      <span title="Kreditkarte – keine Überweisung">
                        <CreditCard className="h-3.5 w-3.5 text-amber-500" />
                      </span>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  <Badge variant={STATUS_VARIANTS[r.status]}>
                    {STATUS_LABELS[r.status]}
                  </Badge>
                </TableCell>
                <TableCell>
                  {r.document_path ? (
                    <button
                      onClick={() => openDocument(`/expense-receipts/${r.id}/document`)}
                      className="text-blue-600 hover:underline text-xs"
                    >
                      Anzeigen
                    </button>
                  ) : (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-xs h-7"
                      onClick={() => onUpload(r)}
                    >
                      <Upload className="h-3 w-3 mr-1" /> Hochladen
                    </Button>
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    {r.status === 'submitted' && (
                      <Button variant="ghost" size="icon" onClick={() => onEdit(r)} title="Bearbeiten">
                        <Pencil className="h-4 w-4" />
                      </Button>
                    )}
                    {isAdmin && r.status === 'submitted' && (
                      <>
                        <Button variant="ghost" size="icon" title="Genehmigen" onClick={() => onApprove(r)}>
                          <CheckCircle className="h-4 w-4 text-green-600" />
                        </Button>
                        <Button variant="ghost" size="icon" title="Ablehnen" onClick={() => onReject(r)}>
                          <XCircle className="h-4 w-4 text-red-600" />
                        </Button>
                      </>
                    )}
                    {isAdmin && r.status === 'paid' && (
                      <Button
                        variant="ghost"
                        size="icon"
                        title="Zurück zu Genehmigt"
                        onClick={() => onReset(r)}
                        className="text-amber-600 hover:text-amber-800"
                      >
                        <RotateCcw className="h-4 w-4" />
                      </Button>
                    )}
                    {isAdmin && onStatusOverride && (
                      <Button
                        variant="ghost"
                        size="icon"
                        title="Status überschreiben (Admin)"
                        onClick={() => onStatusOverride(r)}
                      >
                        <ShieldCheck className="h-4 w-4 text-slate-400 hover:text-slate-700" />
                      </Button>
                    )}
                    {isAdmin && onShowHistory && (
                      <Button
                        variant="ghost"
                        size="icon"
                        title="Änderungsprotokoll"
                        onClick={() => onShowHistory(r)}
                      >
                        <History className="h-4 w-4 text-slate-400 hover:text-slate-700" />
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
  )
}

export function ExpenseReceiptListPage() {
  const queryClient = useQueryClient()
  const { user } = useAuthStore()
  const isAdmin = user?.role === 'admin'

  const [statusFilter, setStatusFilter] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<ExpenseReceipt | null>(null)
  const [uploadReceipt, setUploadReceipt] = useState<ExpenseReceipt | null>(null)
  const [pendingSourceFile, setPendingSourceFile] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  // Admin: Status-Override-Dialog
  const [overrideTarget, setOverrideTarget] = useState<ExpenseReceipt | null>(null)
  const [overrideStatus, setOverrideStatus] = useState<string>('')
  const [overrideNote, setOverrideNote] = useState<string>('')

  // Admin: History-Dialog
  const [historyTarget, setHistoryTarget] = useState<{ id: string; number: string } | null>(null)

  const { data: ownData, isLoading: ownLoading } = useQuery({
    queryKey: ['expense-receipts-own', statusFilter],
    queryFn: () =>
      api.get<ExpenseReceiptListResponse>('/expense-receipts', {
        params: { status: statusFilter || undefined, page_size: 100 },
      }).then((r) => r.data),
  })

  const { data: allData, isLoading: allLoading } = useQuery({
    queryKey: ['expense-receipts-all', statusFilter],
    queryFn: () =>
      api.get<ExpenseReceiptListResponse>('/expense-receipts', {
        params: { status: statusFilter || undefined, page_size: 100 },
      }).then((r) => r.data),
    enabled: isAdmin,
  })

  const { data: pendingData, refetch: refetchPending } = useQuery({
    queryKey: ['expense-receipts-pending'],
    queryFn: () => api.get<{ files: PendingReceipt[] }>('/expense-receipts/pending').then((r) => r.data),
    enabled: isAdmin,
  })
  const pendingFiles = pendingData?.files ?? []

  const { data: usersData } = useQuery({
    queryKey: ['users-all'],
    queryFn: () => api.get<User[]>('/users').then((r) => r.data),
    enabled: isAdmin,
  })
  const users = usersData ?? []

  const { register, handleSubmit, reset, watch, setValue } = useForm<FormData>({
    resolver: zodResolver(schema),
  })

  const watchedPaymentMethod = watch('payment_method')
  const isKreditkarte = watchedPaymentMethod === 'Kreditkarte'
  const watchedSubmittedById = watch('submitted_by_id')

  // IBAN leeren wenn Kreditkarte gewählt wird
  useEffect(() => {
    if (isKreditkarte) {
      setValue('reimbursement_iban', '')
      setValue('reimbursement_account_holder', '')
    }
  }, [isKreditkarte])

  function handleEmployeeChange(userId: string) {
    setValue('submitted_by_id', userId)
    if (!userId || isKreditkarte) return
    const selectedUser = users.find((u) => u.id === userId)
    if (selectedUser?.iban) {
      setValue('reimbursement_iban', selectedUser.iban)
      setValue('reimbursement_account_holder', selectedUser.full_name)
    } else {
      setValue('reimbursement_iban', '')
      setValue('reimbursement_account_holder', '')
    }
  }

  const createMutation = useMutation({
    mutationFn: (payload: FormData & { source_pending_file?: string }) => api.post('/expense-receipts', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expense-receipts'] })
      queryClient.invalidateQueries({ queryKey: ['expense-receipts-pending'] })
      setDialogOpen(false)
      toast({ title: pendingSourceFile ? 'Beleg aus Ordner übernommen' : 'Beleg eingereicht' })
      setPendingSourceFile(null)
    },
    onError: (err: any) => toast({ title: 'Fehler', description: err?.response?.data?.detail, variant: 'destructive' }),
  })

  const deletePendingMutation = useMutation({
    mutationFn: (filename: string) => api.delete(`/expense-receipts/pending/${encodeURIComponent(filename)}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expense-receipts-pending'] })
      toast({ title: 'Datei gelöscht' })
    },
    onError: () => toast({ title: 'Fehler beim Löschen', variant: 'destructive' }),
  })

  const extractPendingMutation = useMutation({
    mutationFn: (filename: string) =>
      api.post(`/expense-receipts/pending/${encodeURIComponent(filename)}/extract`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expense-receipts-pending'] })
      toast({ title: 'Extraktion gestartet' })
    },
    onError: () => toast({ title: 'Fehler bei der Extraktion', variant: 'destructive' }),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: FormData }) => api.put(`/expense-receipts/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expense-receipts'] })
      setDialogOpen(false)
      toast({ title: 'Beleg aktualisiert' })
    },
    onError: (err: any) => toast({ title: 'Fehler', description: err?.response?.data?.detail, variant: 'destructive' }),
  })

  const statusMutation = useMutation({
    mutationFn: ({ id, status, note }: { id: string; status: string; note?: string }) =>
      api.put(`/expense-receipts/${id}/status`, { status, note }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expense-receipts'] })
      toast({ title: 'Status aktualisiert' })
    },
    onError: (err: any) => toast({ title: 'Fehler', description: err?.response?.data?.detail, variant: 'destructive' }),
  })

  const overrideMutation = useMutation({
    mutationFn: ({ id, status, note }: { id: string; status: string; note?: string }) =>
      api.put(`/expense-receipts/${id}/status`, { status, note }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expense-receipts'] })
      setOverrideTarget(null)
      toast({ title: 'Status geändert und protokolliert' })
    },
    onError: (err: any) => toast({ title: 'Fehler', description: err?.response?.data?.detail, variant: 'destructive' }),
  })

  const { data: historyData, isLoading: historyLoading } = useQuery({
    queryKey: ['expense-receipt-history', historyTarget?.id],
    queryFn: () =>
      api.get<StatusChangeLog[]>(`/expense-receipts/${historyTarget!.id}/status-history`).then((r) => r.data),
    enabled: !!historyTarget,
  })

  const uploadMutation = useMutation({
    mutationFn: ({ id, file }: { id: string; file: File }) => {
      const formData = new FormData()
      formData.append('file', file)
      return api.post(`/expense-receipts/${id}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expense-receipts'] })
      setUploadReceipt(null)
      toast({ title: 'Dokument hochgeladen' })
    },
    onError: (err: any) => toast({ title: 'Fehler', description: err?.response?.data?.detail, variant: 'destructive' }),
  })

  function openCreate() {
    setEditing(null)
    setPendingSourceFile(null)
    reset({ receipt_date: new Date().toISOString().slice(0, 10), vat_rate: 19 })
    setDialogOpen(true)
  }

  function openEdit(r: ExpenseReceipt) {
    setEditing(r)
    setPendingSourceFile(null)
    reset({
      receipt_date: r.receipt_date,
      merchant: r.merchant || '',
      amount_gross: parseFloat(r.amount_gross),
      vat_amount: parseFloat(r.vat_amount),
      amount_net: parseFloat(r.amount_net),
      vat_rate: parseFloat(r.vat_rate),
      category: r.category || '',
      description: r.description || '',
      payment_method: r.payment_method || '',
      reimbursement_iban: r.reimbursement_iban || '',
      reimbursement_account_holder: r.reimbursement_account_holder || '',
      notes: r.notes || '',
    })
    setDialogOpen(true)
  }

  function openFromPending(pf: PendingReceipt) {
    setEditing(null)
    setPendingSourceFile(pf.filename)
    const d = pf.extracted ?? {}
    reset({
      receipt_date: d.receipt_date ?? new Date().toISOString().slice(0, 10),
      merchant: d.merchant ?? '',
      amount_gross: parseFloat(String(d.amount_gross ?? '0')) || 0,
      vat_amount: parseFloat(String(d.vat_amount ?? '0')) || 0,
      amount_net: parseFloat(String(d.amount_net ?? '0')) || 0,
      vat_rate: parseFloat(String(d.vat_rate ?? '19')) || 19,
      category: d.category ?? '',
      description: d.description ?? '',
      payment_method: d.payment_method ?? '',
      reimbursement_iban: '',
      reimbursement_account_holder: '',
      notes: '',
      submitted_by_id: user?.id ?? '',
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

  function handleUpload(r: ExpenseReceipt) {
    setUploadReceipt(r)
    fileRef.current?.click()
  }

  const ownItems = ownData?.items ?? []
  const allItems = allData?.items ?? []
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Belege</h1>
          <p className="text-sm text-slate-500 mt-1">Ausgaben und Erstattungen</p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4 mr-2" /> Beleg einreichen
        </Button>
      </div>

      {/* Pending-Panel: Belege aus dem Ordner */}
      {isAdmin && pendingFiles.length > 0 && (
        <div className="border border-amber-200 bg-amber-50 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="font-semibold text-amber-900 text-sm">
              Eingang Ordner – {pendingFiles.length} Beleg(e) warten auf Übernahme
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
                      {pf.extracted.merchant && <span>Händler: <strong>{pf.extracted.merchant}</strong></span>}
                      {pf.extracted.amount_gross && <span>Betrag: <strong>{formatCurrency(String(pf.extracted.amount_gross))}</strong></span>}
                      {pf.extracted.receipt_date && <span>Datum: {pf.extracted.receipt_date}</span>}
                      {pf.extracted.category && <span className="text-slate-400">{pf.extracted.category}</span>}
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
                    onClick={() => openDocument(`/expense-receipts/pending/${encodeURIComponent(pf.filename)}/download`)}
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
                    title="Als Beleg übernehmen"
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

      <div>
        <select
          className="border rounded-md px-3 py-2 text-sm bg-background"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">Alle Status</option>
          {Object.entries(STATUS_LABELS).map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
      </div>

      {isAdmin ? (
        <Tabs defaultValue="all">
          <TabsList>
            <TabsTrigger value="all">Alle Belege ({allItems.length})</TabsTrigger>
            <TabsTrigger value="own">Meine Belege ({ownItems.length})</TabsTrigger>
          </TabsList>
          <TabsContent value="all" className="mt-4">
            <ReceiptTable
              items={allItems}
              isLoading={allLoading}
              isAdmin={true}
              onEdit={openEdit}
              onApprove={(r) => statusMutation.mutate({ id: r.id, status: 'approved' })}
              onReject={(r) => statusMutation.mutate({ id: r.id, status: 'rejected' })}
              onUpload={handleUpload}
              onReset={(r) => statusMutation.mutate({ id: r.id, status: 'approved' })}
              onStatusOverride={(r) => { setOverrideStatus(r.status); setOverrideNote(''); setOverrideTarget(r) }}
              onShowHistory={(r) => setHistoryTarget({ id: r.id, number: r.receipt_number })}
            />
          </TabsContent>
          <TabsContent value="own" className="mt-4">
            <ReceiptTable
              items={ownItems}
              isLoading={ownLoading}
              isAdmin={false}
              onEdit={openEdit}
              onApprove={(r) => statusMutation.mutate({ id: r.id, status: 'approved' })}
              onReject={(r) => statusMutation.mutate({ id: r.id, status: 'rejected' })}
              onUpload={handleUpload}
              onReset={() => {}}
            />
          </TabsContent>
        </Tabs>
      ) : (
        <ReceiptTable
          items={ownItems}
          isLoading={ownLoading}
          isAdmin={false}
          onEdit={openEdit}
          onApprove={() => {}}
          onReject={() => {}}
          onUpload={handleUpload}
          onReset={() => {}}
        />
      )}

      {/* Admin: Status-Override-Dialog */}
      <Dialog open={!!overrideTarget} onOpenChange={(o) => !o && setOverrideTarget(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Status überschreiben (Admin)</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="text-sm text-muted-foreground">
              Beleg: <span className="font-mono font-medium">{overrideTarget?.receipt_number}</span>
              {' – '}Aktuell:{' '}
              <span className="font-medium">{overrideTarget ? STATUS_LABELS[overrideTarget.status] : ''}</span>
            </div>
            <div className="space-y-2">
              <Label>Neuer Status</Label>
              <select
                className="w-full border rounded-md px-3 py-2 text-sm bg-background"
                value={overrideStatus}
                onChange={(e) => setOverrideStatus(e.target.value)}
              >
                {Object.entries(STATUS_LABELS).map(([v, l]) => (
                  <option key={v} value={v}>{l}</option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label>Begründung <span className="text-muted-foreground font-normal">(optional)</span></Label>
              <Input
                value={overrideNote}
                onChange={(e) => setOverrideNote(e.target.value)}
                placeholder="z.B. Fehler korrigiert…"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOverrideTarget(null)}>Abbrechen</Button>
            <Button
              onClick={() => overrideTarget && overrideMutation.mutate({
                id: overrideTarget.id,
                status: overrideStatus,
                note: overrideNote || undefined,
              })}
              disabled={overrideMutation.isPending || !overrideStatus || overrideStatus === overrideTarget?.status}
            >
              {overrideMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Speichern
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Admin: Statusprotokoll-Dialog */}
      <Dialog open={!!historyTarget} onOpenChange={(o) => !o && setHistoryTarget(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              Statusprotokoll – <span className="font-mono">{historyTarget?.number}</span>
            </DialogTitle>
          </DialogHeader>
          <div className="py-2 space-y-2 max-h-96 overflow-y-auto">
            {historyLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : !historyData || historyData.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-6">Keine Statusänderungen protokolliert.</p>
            ) : (
              historyData.map((h) => (
                <div key={h.id} className="flex items-start gap-3 text-sm border rounded-md px-3 py-2">
                  <div className="flex-1 min-w-0">
                    <div>
                      <span className="font-medium">{STATUS_LABELS[h.from_status as ExpenseReceiptStatus] ?? h.from_status}</span>
                      <span className="mx-2 text-muted-foreground">→</span>
                      <span className="font-medium">{STATUS_LABELS[h.to_status as ExpenseReceiptStatus] ?? h.to_status}</span>
                    </div>
                    {h.note && <p className="text-xs text-muted-foreground mt-0.5 truncate">{h.note}</p>}
                  </div>
                  <div className="text-xs text-muted-foreground shrink-0 text-right">
                    <div>{h.changed_by?.full_name ?? '–'}</div>
                    <div>{new Date(h.changed_at).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' })}</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Hidden file input */}
      <input
        ref={fileRef}
        type="file"
        accept=".pdf,.jpg,.jpeg,.png"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file && uploadReceipt) {
            uploadMutation.mutate({ id: uploadReceipt.id, file })
          }
          e.target.value = ''
        }}
      />

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] flex flex-col">
          <DialogHeader className="shrink-0">
            <DialogTitle>
              {editing ? 'Beleg bearbeiten' : pendingSourceFile ? 'Beleg aus Ordner übernehmen' : 'Beleg einreichen'}
            </DialogTitle>
            {pendingSourceFile && (
              <p className="text-xs text-muted-foreground mt-1">Datei: {pendingSourceFile}</p>
            )}
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col flex-1 overflow-hidden">
            <div className="flex-1 overflow-y-auto pr-1 space-y-4">
            {/* Eingereicht von: nur bei Pending-Übernahme durch Admin */}
            {pendingSourceFile && isAdmin && (
              <div className="space-y-2 rounded-md border px-3 py-2 bg-slate-50">
                <Label>Eingereicht von</Label>
                <select
                  className="w-full border rounded-md px-3 py-2 text-sm bg-background"
                  value={watchedSubmittedById || ''}
                  onChange={(e) => handleEmployeeChange(e.target.value)}
                >
                  <option value="">– Mich selbst (Admin) –</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>{u.full_name} ({u.email})</option>
                  ))}
                </select>
                <p className="text-xs text-muted-foreground">
                  Die IBAN wird automatisch aus dem Mitarbeiterstamm übernommen.
                </p>
              </div>
            )}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Belegdatum *</Label>
                <Input type="date" {...register('receipt_date')} />
              </div>
              <div className="space-y-2">
                <Label>Händler / Lieferant</Label>
                <Input {...register('merchant')} placeholder="Name des Händlers" />
              </div>
              <div className="space-y-2">
                <Label>Kategorie</Label>
                <select className="w-full border rounded-md px-3 py-2 text-sm bg-background" {...register('category')}>
                  <option value="">Bitte wählen...</option>
                  {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div className="space-y-2">
                <Label>Zahlungsart</Label>
                <select className="w-full border rounded-md px-3 py-2 text-sm bg-background" {...register('payment_method')}>
                  <option value="">–</option>
                  <option value="Bar">Bar</option>
                  <option value="EC-Karte">EC-Karte</option>
                  <option value="Kreditkarte">Kreditkarte</option>
                  <option value="Überweisung">Überweisung</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label>Brutto-Betrag *</Label>
                <Input type="number" step="0.01" {...register('amount_gross')} />
              </div>
              <div className="space-y-2">
                <Label>MwSt.-Satz (%)</Label>
                <Input type="number" step="0.01" {...register('vat_rate')} />
              </div>
              <div className="space-y-2">
                <Label>MwSt.-Betrag</Label>
                <Input type="number" step="0.01" {...register('vat_amount')} />
              </div>
              <div className="space-y-2">
                <Label>Netto-Betrag</Label>
                <Input type="number" step="0.01" {...register('amount_net')} />
              </div>
              <div className="col-span-2 space-y-2">
                <Label>Beschreibung / Verwendungszweck</Label>
                <Input {...register('description')} />
              </div>
            </div>

            <div className="border-t pt-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-sm font-semibold text-slate-700">Bankverbindung für Erstattung</span>
                {isKreditkarte && (
                  <span className="inline-flex items-center gap-1 text-xs bg-amber-100 text-amber-800 px-2 py-0.5 rounded-full">
                    <CreditCard className="h-3 w-3" />
                    Kreditkarte – keine Überweisung
                  </span>
                )}
              </div>
              {isKreditkarte ? (
                <p className="text-sm text-slate-500 bg-slate-50 border rounded-md px-3 py-2">
                  Bei Kreditkartenzahlungen erfolgt keine Erstattung per Überweisung. Dieser Beleg wird beim SEPA-Export nicht berücksichtigt.
                </p>
              ) : (
                <div className="grid grid-cols-2 gap-4">
                  <div className="col-span-2 space-y-2">
                    <Label>IBAN</Label>
                    <Input {...register('reimbursement_iban')} placeholder="DE..." className="font-mono" />
                  </div>
                  <div className="col-span-2 space-y-2">
                    <Label>Kontoinhaber</Label>
                    <Input {...register('reimbursement_account_holder')} />
                  </div>
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label>Notizen</Label>
              <Input {...register('notes')} />
            </div>
            </div>
            <DialogFooter className="shrink-0 pt-4">
              <Button variant="outline" type="button" onClick={() => setDialogOpen(false)}>Abbrechen</Button>
              <Button type="submit" disabled={createMutation.isPending || updateMutation.isPending}>
                {(createMutation.isPending || updateMutation.isPending) && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {editing ? 'Speichern' : pendingSourceFile ? 'Übernehmen' : 'Einreichen'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
