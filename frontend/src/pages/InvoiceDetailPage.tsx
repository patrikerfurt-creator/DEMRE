import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Download, FileCode, FileMinus, Loader2, Pencil, Plus, Trash2, X } from 'lucide-react'
import api from '@/lib/api'
import type { Invoice, InvoiceItem, InvoiceStatus } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { toast } from '@/hooks/use-toast'
import {
  formatDate, formatCurrency, formatApiError, allowedTransitions,
  INVOICE_STATUS_LABELS, INVOICE_STATUS_COLORS, DOCUMENT_TEXTS,
} from '@/lib/utils'

const EMPTY_ITEM_FORM = {
  description: '',
  additional_text: '',
  quantity: '1',
  unit: '',
  unit_price_net: '',
  vat_rate: '19',
  total_net: '',
  total_vat: '',
  total_gross: '',
}

function calcTotals(form: typeof EMPTY_ITEM_FORM) {
  const qty = parseFloat(form.quantity) || 0
  const price = parseFloat(form.unit_price_net) || 0
  const vat = parseFloat(form.vat_rate) || 0
  const net = Math.round(qty * price * 100) / 100
  const vatAmt = Math.round(net * vat) / 100
  const gross = Math.round((net + vatAmt) * 100) / 100
  return { net, vatAmt, gross }
}

export function InvoiceDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [itemDialogOpen, setItemDialogOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<InvoiceItem | null>(null)
  const [itemForm, setItemForm] = useState(EMPTY_ITEM_FORM)
  const [creditDialogOpen, setCreditDialogOpen] = useState(false)
  const [creditReason, setCreditReason] = useState('')

  const { data: invoice, isLoading } = useQuery({
    queryKey: ['invoice', id],
    queryFn: () => api.get<Invoice>(`/invoices/${id}`).then((r) => r.data),
    enabled: !!id,
  })

  const statusMutation = useMutation({
    mutationFn: (status: InvoiceStatus) => api.put(`/invoices/${id}/status`, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoice', id] })
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
      toast({ title: 'Status aktualisiert' })
    },
    onError: (err: any) => {
      toast({ title: 'Fehler', description: formatApiError(err), variant: 'destructive' })
    },
  })

  const creditNoteMutation = useMutation({
    mutationFn: (reason: string) =>
      api.post<Invoice>(`/invoices/${id}/credit-note`, { credit_reason: reason }),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['invoice', id] })
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
      setCreditDialogOpen(false)
      setCreditReason('')
      toast({
        title: `Gutschrift ${res.data.invoice_number} als Entwurf erstellt`,
        description: 'Positionen sind noch änderbar. Beim Ausstellen wird die Rechnung storniert.',
      })
      navigate(`/credit-notes/${res.data.id}`)
    },
    onError: (err: any) => {
      toast({ title: 'Fehler', description: formatApiError(err), variant: 'destructive' })
    },
  })

  const saveItemMutation = useMutation({
    mutationFn: (data: any) =>
      editingItem
        ? api.put(`/invoices/${id}/items/${editingItem.id}`, data)
        : api.post(`/invoices/${id}/items`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoice', id] })
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
      setItemDialogOpen(false)
      setEditingItem(null)
      toast({ title: editingItem ? 'Position aktualisiert' : 'Position hinzugefügt' })
    },
    onError: (err: any) => {
      toast({ title: 'Fehler', description: formatApiError(err), variant: 'destructive' })
    },
  })

  const deleteItemMutation = useMutation({
    mutationFn: (itemId: string) => api.delete(`/invoices/${id}/items/${itemId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoice', id] })
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
      toast({ title: 'Position gelöscht' })
    },
    onError: (err: any) => {
      toast({ title: 'Fehler', description: formatApiError(err), variant: 'destructive' })
    },
  })

  function openAddItem() {
    setEditingItem(null)
    setItemForm(EMPTY_ITEM_FORM)
    setItemDialogOpen(true)
  }

  function openEditItem(item: InvoiceItem) {
    setEditingItem(item)
    setItemForm({
      description: item.description,
      additional_text: item.additional_text || '',
      quantity: String(parseFloat(item.quantity)),
      unit: item.unit || '',
      unit_price_net: String(parseFloat(item.unit_price_net)),
      vat_rate: String(parseFloat(item.vat_rate)),
      total_net: item.total_net,
      total_vat: item.total_vat,
      total_gross: item.total_gross,
    })
    setItemDialogOpen(true)
  }

  function handleItemFormChange(field: string, value: string) {
    const updated = { ...itemForm, [field]: value }
    if (['quantity', 'unit_price_net', 'vat_rate'].includes(field)) {
      const { net, vatAmt, gross } = calcTotals(updated)
      updated.total_net = String(net)
      updated.total_vat = String(vatAmt)
      updated.total_gross = String(gross)
    }
    setItemForm(updated)
  }

  function handleItemSubmit(e: React.FormEvent) {
    e.preventDefault()
    const { net, vatAmt, gross } = calcTotals(itemForm)
    saveItemMutation.mutate({
      description: itemForm.description,
      additional_text: itemForm.additional_text || null,
      quantity: parseFloat(itemForm.quantity),
      unit: itemForm.unit || null,
      unit_price_net: parseFloat(itemForm.unit_price_net),
      vat_rate: parseFloat(itemForm.vat_rate),
      total_net: net,
      total_vat: vatAmt,
      total_gross: gross,
    })
  }

  async function downloadPdf() {
    try {
      const res = await api.get(`/invoices/${id}/pdf`, { responseType: 'blob' })
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
      const a = document.createElement('a')
      a.href = url
      a.download = `${invoice?.invoice_number || 'rechnung'}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast({ title: 'Fehler beim PDF-Download', variant: 'destructive' })
    }
  }

  async function downloadXml() {
    try {
      const res = await api.get(`/invoices/${id}/xml`, { responseType: 'blob' })
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/xml' }))
      const a = document.createElement('a')
      a.href = url
      a.download = `${invoice?.invoice_number || 'rechnung'}.xml`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast({ title: 'Fehler beim XML-Download', variant: 'destructive' })
    }
  }

  if (isLoading) return <div className="p-6 text-muted-foreground">Lädt...</div>
  if (!invoice) return <div className="p-6 text-muted-foreground">Beleg nicht gefunden</div>

  const documentType = invoice.document_type ?? 'invoice'
  const isCreditNote = documentType === 'credit_note'
  const texts = DOCUMENT_TEXTS[documentType]
  const transitions = allowedTransitions(documentType, invoice.status)
  // Gutschrift nur zu einer ausgestellten Rechnung, die noch keine hat
  const canCreateCreditNote =
    !isCreditNote &&
    !invoice.credit_note &&
    ['issued', 'sent', 'paid', 'overdue'].includes(invoice.status)

  const isDraft = invoice.status === 'draft'
  const subtotal = parseFloat(invoice.subtotal_net)
  const vatTotal = parseFloat(invoice.total_vat)
  const gross = parseFloat(invoice.total_gross)

  const vatGroups: Record<string, { net: number; vat: number; rate: string }> = {}
  invoice.items.forEach((item) => {
    const rate = item.vat_rate
    if (!vatGroups[rate]) vatGroups[rate] = { net: 0, vat: 0, rate }
    vatGroups[rate].net += parseFloat(item.total_net)
    vatGroups[rate].vat += parseFloat(item.total_vat)
  })

  const { net: previewNet, vatAmt: previewVat, gross: previewGross } = calcTotals(itemForm)

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate(isCreditNote ? '/credit-notes' : '/invoices')}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{invoice.invoice_number}</h1>
          <p className="text-sm text-slate-500">
            {texts.singular} vom {formatDate(invoice.invoice_date)}
          </p>
          {isCreditNote && invoice.credit_note_of_id && (
            <button
              type="button"
              className="text-sm text-blue-600 hover:underline"
              onClick={() => navigate(`/invoices/${invoice.credit_note_of_id}`)}
            >
              Gutschrift zu Rechnung {invoice.credit_note_of_number ?? ''}
            </button>
          )}
          {!isCreditNote && invoice.credit_note && (
            <button
              type="button"
              className="text-sm text-blue-600 hover:underline"
              onClick={() => navigate(`/credit-notes/${invoice.credit_note!.id}`)}
            >
              {invoice.status === 'cancelled' ? 'Storniert durch' : 'Gutschrift (Entwurf):'}{' '}
              Gutschrift {invoice.credit_note.invoice_number}
            </button>
          )}
        </div>
        <span className={`ml-auto px-3 py-1 rounded-full text-sm font-medium ${INVOICE_STATUS_COLORS[invoice.status]}`}>
          {INVOICE_STATUS_LABELS[invoice.status]}
        </span>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Status:</span>
          <Select
            value={invoice.status}
            onValueChange={(v) => statusMutation.mutate(v as InvoiceStatus)}
            disabled={statusMutation.isPending || transitions.length === 0}
          >
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={invoice.status}>{INVOICE_STATUS_LABELS[invoice.status]}</SelectItem>
              {transitions.map((s) => (
                <SelectItem key={s} value={s}>{INVOICE_STATUS_LABELS[s]}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button variant="outline" size="sm" onClick={downloadPdf}>
          <Download className="h-4 w-4 mr-2" /> PDF
        </Button>
        <Button variant="outline" size="sm" onClick={downloadXml}>
          <FileCode className="h-4 w-4 mr-2" /> ZUGFeRD XML
        </Button>
        {canCreateCreditNote && (
          <Button variant="outline" size="sm" onClick={() => setCreditDialogOpen(true)}>
            <FileMinus className="h-4 w-4 mr-2" /> Gutschrift erstellen
          </Button>
        )}
      </div>

      {/* Metadata */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="text-xs text-muted-foreground">{texts.dateLabel}</div>
            <div className="font-medium">{formatDate(invoice.invoice_date)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            {isCreditNote ? (
              <>
                <div className="text-xs text-muted-foreground">Gutschriftsgrund</div>
                <div className="font-medium text-sm">{invoice.credit_reason || '–'}</div>
              </>
            ) : (
              <>
                <div className="text-xs text-muted-foreground">Fälligkeitsdatum</div>
                <div className="font-medium">{formatDate(invoice.due_date)}</div>
              </>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-xs text-muted-foreground">Leistungszeitraum</div>
            <div className="font-medium text-sm">
              {invoice.billing_period_from
                ? `${formatDate(invoice.billing_period_from)} – ${formatDate(invoice.billing_period_to)}`
                : '–'}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-xs text-muted-foreground">Währung</div>
            <div className="font-medium">{invoice.currency}</div>
          </CardContent>
        </Card>
      </div>

      {/* Line items */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <CardTitle className="text-base">{texts.itemsTitle}</CardTitle>
          {isDraft && (
            <Button size="sm" onClick={openAddItem}>
              <Plus className="h-4 w-4 mr-2" /> Position hinzufügen
            </Button>
          )}
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">Pos.</TableHead>
                <TableHead>Beschreibung</TableHead>
                <TableHead className="text-right">Menge</TableHead>
                <TableHead className="w-28">Einheit</TableHead>
                <TableHead className="text-right w-20">EP netto</TableHead>
                <TableHead className="text-right">MwSt.</TableHead>
                <TableHead className="text-right">Gesamt netto</TableHead>
                <TableHead className="text-right">Gesamt brutto</TableHead>
                {isDraft && <TableHead className="w-20" />}
              </TableRow>
            </TableHeader>
            <TableBody>
              {invoice.items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="text-sm text-muted-foreground">{item.position}</TableCell>
                  <TableCell className="break-words max-w-xs">
                    <div>{item.description}</div>
                    {item.additional_text && (
                      <div className="text-xs text-muted-foreground mt-0.5 italic">{item.additional_text}</div>
                    )}
                  </TableCell>
                  <TableCell className="text-right">{String(parseFloat(item.quantity))}</TableCell>
                  <TableCell>{item.unit || '–'}</TableCell>
                  <TableCell className="text-right">{formatCurrency(item.unit_price_net)}</TableCell>
                  <TableCell className="text-right">{parseFloat(item.vat_rate).toFixed(0)}%</TableCell>
                  <TableCell className="text-right">{formatCurrency(item.total_net)}</TableCell>
                  <TableCell className="text-right font-medium">{formatCurrency(item.total_gross)}</TableCell>
                  {isDraft && (
                    <TableCell>
                      <div className="flex gap-1 justify-end">
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEditItem(item)}>
                          <Pencil className="h-3 w-3" />
                        </Button>
                        <Button
                          variant="ghost" size="icon" className="h-7 w-7"
                          onClick={() => { if (confirm('Position löschen?')) deleteItemMutation.mutate(item.id) }}
                          disabled={deleteItemMutation.isPending}
                        >
                          <Trash2 className="h-3 w-3 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Totals */}
      <div className="flex justify-end">
        <div className="w-80 space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Zwischensumme netto</span>
            <span>{formatCurrency(subtotal)}</span>
          </div>
          {Object.values(vatGroups).map((g) => (
            <div key={g.rate} className="flex justify-between text-sm">
              <span className="text-muted-foreground">MwSt. {parseFloat(g.rate).toFixed(0)}% auf {formatCurrency(g.net)}</span>
              <span>{formatCurrency(g.vat)}</span>
            </div>
          ))}
          <div className="border-t pt-2 flex justify-between font-semibold text-base">
            <span>{texts.totalLabel}</span>
            <span>{formatCurrency(gross)}</span>
          </div>
        </div>
      </div>

      {/* Notes */}
      {(invoice.notes || invoice.internal_notes) && (
        <Card>
          <CardContent className="pt-4 space-y-2">
            {invoice.notes && (
              <div>
                <div className="text-xs text-muted-foreground mb-1">Hinweise</div>
                <div className="text-sm">{invoice.notes}</div>
              </div>
            )}
            {invoice.internal_notes && (
              <div>
                <div className="text-xs text-muted-foreground mb-1">Interne Notizen</div>
                <div className="text-sm">{invoice.internal_notes}</div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Gutschrift erstellen */}
      <Dialog open={creditDialogOpen} onOpenChange={setCreditDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Gutschrift zu Rechnung {invoice.invoice_number}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Es werden alle {invoice.items.length} Positionen über{' '}
              {formatCurrency(gross)} übernommen. Die Gutschrift entsteht als
              Entwurf – Positionen kannst du dort noch ändern oder löschen.
              Beim Ausstellen einer vollen Gutschrift wird diese Rechnung
              automatisch storniert.
            </p>
            <div>
              <Label htmlFor="credit-reason">Gutschriftsgrund *</Label>
              <textarea
                id="credit-reason"
                className="mt-1 w-full min-h-[80px] rounded-md border border-input bg-background px-3 py-2 text-sm"
                placeholder="z.B. Leistung wurde nicht erbracht"
                value={creditReason}
                onChange={(e) => setCreditReason(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreditDialogOpen(false)}>
              Abbrechen
            </Button>
            <Button
              disabled={!creditReason.trim() || creditNoteMutation.isPending}
              onClick={() => creditNoteMutation.mutate(creditReason.trim())}
            >
              {creditNoteMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Gutschrift erstellen
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Item Edit Dialog (draft only) */}
      <Dialog open={itemDialogOpen} onOpenChange={(open) => { setItemDialogOpen(open); if (!open) setEditingItem(null) }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editingItem ? 'Position bearbeiten' : 'Position hinzufügen'}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleItemSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label>Beschreibung *</Label>
              <Input
                value={itemForm.description}
                onChange={(e) => handleItemFormChange('description', e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label>Zusatztext <span className="text-muted-foreground font-normal">(optional, erscheint in der Rechnung)</span></Label>
              <textarea
                className="flex min-h-[72px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                value={itemForm.additional_text}
                onChange={(e) => handleItemFormChange('additional_text', e.target.value)}
                placeholder="z.B. Miete Wohnung EG links, Objekt Musterstraße 1"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Menge</Label>
                <Input
                  type="number" step="0.001"
                  className="[appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  value={itemForm.quantity}
                  onChange={(e) => handleItemFormChange('quantity', e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Einheit</Label>
                <Input value={itemForm.unit} onChange={(e) => handleItemFormChange('unit', e.target.value)} placeholder="z.B. Stk, h, m²" />
              </div>
              <div className="space-y-2">
                <Label>EP netto (€)</Label>
                <Input
                  type="number" step="0.0001"
                  className="[appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  value={itemForm.unit_price_net}
                  onChange={(e) => handleItemFormChange('unit_price_net', e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>MwSt. (%)</Label>
                <Input
                  type="number" step="0.01"
                  className="[appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  value={itemForm.vat_rate}
                  onChange={(e) => handleItemFormChange('vat_rate', e.target.value)}
                />
              </div>
            </div>
            {itemForm.unit_price_net && (
              <div className="rounded-md bg-slate-50 px-3 py-2 text-sm space-y-1">
                <div className="flex justify-between text-muted-foreground">
                  <span>Netto</span><span>{formatCurrency(previewNet)}</span>
                </div>
                <div className="flex justify-between text-muted-foreground">
                  <span>MwSt.</span><span>{formatCurrency(previewVat)}</span>
                </div>
                <div className="flex justify-between font-medium">
                  <span>Brutto</span><span>{formatCurrency(previewGross)}</span>
                </div>
              </div>
            )}
            <DialogFooter>
              <Button variant="outline" type="button" onClick={() => setItemDialogOpen(false)}>Abbrechen</Button>
              <Button type="submit" disabled={saveItemMutation.isPending}>
                {saveItemMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {editingItem ? 'Speichern' : 'Hinzufügen'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
