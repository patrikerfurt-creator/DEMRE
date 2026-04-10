import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Plus, Upload, Pencil, CheckCircle, XCircle, Loader2, Download } from 'lucide-react'
import api from '@/lib/api'
import type { ExpenseReceipt, ExpenseReceiptListResponse, ExpenseReceiptStatus } from '@/types'
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
}: {
  items: ExpenseReceipt[]
  isLoading: boolean
  isAdmin: boolean
  onEdit: (r: ExpenseReceipt) => void
  onApprove: (r: ExpenseReceipt) => void
  onReject: (r: ExpenseReceipt) => void
  onUpload: (r: ExpenseReceipt) => void
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
                <TableCell className="text-right font-medium">{formatCurrency(r.amount_gross)}</TableCell>
                <TableCell>
                  <Badge variant={STATUS_VARIANTS[r.status]}>
                    {STATUS_LABELS[r.status]}
                  </Badge>
                </TableCell>
                <TableCell>
                  {r.document_path ? (
                    <a
                      href={`/api/v1/expense-receipts/${r.id}/document`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline text-xs"
                    >
                      Anzeigen
                    </a>
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
  const fileRef = useRef<HTMLInputElement>(null)

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

  const { register, handleSubmit, reset } = useForm<FormData>({
    resolver: zodResolver(schema),
  })

  const createMutation = useMutation({
    mutationFn: (data: FormData) => api.post('/expense-receipts', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expense-receipts'] })
      setDialogOpen(false)
      toast({ title: 'Beleg eingereicht' })
    },
    onError: (err: any) => toast({ title: 'Fehler', description: err?.response?.data?.detail, variant: 'destructive' }),
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
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.put(`/expense-receipts/${id}/status`, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expense-receipts'] })
      toast({ title: 'Status aktualisiert' })
    },
    onError: (err: any) => toast({ title: 'Fehler', description: err?.response?.data?.detail, variant: 'destructive' }),
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

  const sepaExportMutation = useMutation({
    mutationFn: () => api.post('/expense-receipts/sepa-export', null, { responseType: 'blob' }),
    onSuccess: (res) => {
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `sepa_belege_${new Date().toISOString().slice(0, 10)}.xml`
      a.click()
      URL.revokeObjectURL(url)
      queryClient.invalidateQueries({ queryKey: ['expense-receipts'] })
      toast({ title: 'SEPA-Export erstellt' })
    },
    onError: (err: any) => toast({ title: 'Fehler', description: err?.response?.data?.detail, variant: 'destructive' }),
  })

  function openCreate() {
    setEditing(null)
    reset({ receipt_date: new Date().toISOString().slice(0, 10), vat_rate: 19 })
    setDialogOpen(true)
  }

  function openEdit(r: ExpenseReceipt) {
    setEditing(r)
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

  function onSubmit(data: FormData) {
    if (editing) {
      updateMutation.mutate({ id: editing.id, data })
    } else {
      createMutation.mutate(data)
    }
  }

  function handleUpload(r: ExpenseReceipt) {
    setUploadReceipt(r)
    fileRef.current?.click()
  }

  const ownItems = ownData?.items ?? []
  const allItems = allData?.items ?? []
  const approvedCount = allItems.filter(r => r.status === 'approved' && r.reimbursement_iban).length

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Belege</h1>
          <p className="text-sm text-slate-500 mt-1">Ausgaben und Erstattungen</p>
        </div>
        <div className="flex gap-2">
          {isAdmin && approvedCount > 0 && (
            <Button variant="outline" onClick={() => sepaExportMutation.mutate()}>
              {sepaExportMutation.isPending
                ? <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                : <Download className="h-4 w-4 mr-2" />}
              SEPA Erstattungen ({approvedCount})
            </Button>
          )}
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4 mr-2" /> Beleg einreichen
          </Button>
        </div>
      </div>

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
        />
      )}

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
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editing ? 'Beleg bearbeiten' : 'Beleg einreichen'}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
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
              <div className="text-sm font-semibold text-slate-700 mb-3">Bankverbindung für Erstattung</div>
              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2 space-y-2">
                  <Label>IBAN</Label>
                  <Input {...register('reimbursement_iban')} placeholder="DE..." />
                </div>
                <div className="col-span-2 space-y-2">
                  <Label>Kontoinhaber</Label>
                  <Input {...register('reimbursement_account_holder')} />
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <Label>Notizen</Label>
              <Input {...register('notes')} />
            </div>

            <DialogFooter>
              <Button variant="outline" type="button" onClick={() => setDialogOpen(false)}>Abbrechen</Button>
              <Button type="submit" disabled={createMutation.isPending || updateMutation.isPending}>
                {(createMutation.isPending || updateMutation.isPending) && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {editing ? 'Speichern' : 'Einreichen'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
