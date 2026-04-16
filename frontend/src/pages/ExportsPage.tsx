import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Download, Loader2, FileText, Euro, CreditCard, Users } from 'lucide-react'
import api from '@/lib/api'
import type { IncomingInvoice, IncomingInvoiceListResponse, ExpenseReceipt, ExpenseReceiptListResponse, PaymentRun } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { toast } from '@/hooks/use-toast'
import { formatDate, formatCurrency } from '@/lib/utils'

function creditorName(c?: { company_name?: string; first_name?: string; last_name?: string }) {
  if (!c) return '–'
  return c.company_name || [c.first_name, c.last_name].filter(Boolean).join(' ') || '–'
}

export function ExportsPage() {
  const queryClient = useQueryClient()

  // SEPA Zahlungen
  const [sepaExecDate, setSepaExecDate] = useState('')
  const [selectedInvoiceIds, setSelectedInvoiceIds] = useState<Set<string>>(new Set())
  const [selectedReceiptIds, setSelectedReceiptIds] = useState<Set<string>>(new Set())

  // DATEV
  const [datevFrom, setDatevFrom] = useState('')
  const [datevTo, setDatevTo] = useState('')

  // ── Daten laden ─────────────────────────────────────────────────────────────
  const { data: invoicesData } = useQuery({
    queryKey: ['incoming-invoices-approved'],
    queryFn: () =>
      api.get<IncomingInvoiceListResponse>('/incoming-invoices', {
        params: { status: 'approved', page_size: 100 },
      }).then((r) => r.data),
  })

  const { data: receiptsData } = useQuery({
    queryKey: ['expense-receipts-approved'],
    queryFn: () =>
      api.get<ExpenseReceiptListResponse>('/expense-receipts', {
        params: { status: 'approved', page_size: 100 },
      }).then((r) => r.data),
  })

  const { data: runsData } = useQuery({
    queryKey: ['payment-runs'],
    queryFn: () => api.get<PaymentRun[]>('/payment-runs?page_size=20').then((r) => r.data),
  })

  // Gefilterte Listen
  const payableInvoices = (invoicesData?.items ?? []).filter(
    (inv) => !inv.is_direct_debit && inv.creditor?.iban
  )
  const payableReceipts = (receiptsData?.items ?? []).filter(
    (r) => r.reimbursement_iban && r.payment_method !== 'Kreditkarte'
  )
  const runs = Array.isArray(runsData) ? runsData : []

  // ── Auswahl-Hilfsfunktionen ─────────────────────────────────────────────────
  function toggleInvoice(id: string) {
    setSelectedInvoiceIds((prev) => { const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s })
  }
  function toggleReceipt(id: string) {
    setSelectedReceiptIds((prev) => { const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s })
  }
  function selectAllInvoices() { setSelectedInvoiceIds(new Set(payableInvoices.map((i) => i.id))) }
  function selectAllReceipts() { setSelectedReceiptIds(new Set(payableReceipts.map((r) => r.id))) }
  function clearAll() { setSelectedInvoiceIds(new Set()); setSelectedReceiptIds(new Set()) }

  // Summen
  const invoicesTotal = payableInvoices
    .filter((i) => selectedInvoiceIds.has(i.id))
    .reduce((s, i) => s + parseFloat(i.total_gross), 0)
  const receiptsTotal = payableReceipts
    .filter((r) => selectedReceiptIds.has(r.id))
    .reduce((s, r) => s + parseFloat(r.amount_gross), 0)
  const grandTotal = invoicesTotal + receiptsTotal
  const totalCount = selectedInvoiceIds.size + selectedReceiptIds.size

  // ── SEPA Export ─────────────────────────────────────────────────────────────
  const sepaExportMutation = useMutation({
    mutationFn: () =>
      api.post('/sepa/payment-export', {
        incoming_invoice_ids: Array.from(selectedInvoiceIds),
        expense_receipt_ids: Array.from(selectedReceiptIds),
        execution_date: sepaExecDate || undefined,
      }, { responseType: 'blob' }),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['incoming-invoices-approved'] })
      queryClient.invalidateQueries({ queryKey: ['expense-receipts-approved'] })
      queryClient.invalidateQueries({ queryKey: ['payment-runs'] })
      queryClient.invalidateQueries({ queryKey: ['incoming-invoices'] })
      queryClient.invalidateQueries({ queryKey: ['expense-receipts'] })
      clearAll()
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/xml' }))
      const a = document.createElement('a')
      a.href = url
      a.download = `sepa_zahlung_${new Date().toISOString().slice(0, 10)}.xml`
      a.click()
      URL.revokeObjectURL(url)
      toast({ title: 'SEPA-Datei erstellt und heruntergeladen' })
    },
    onError: (err: any) => {
      const detail = err?.response?.data
      let msg = 'Unbekannter Fehler'
      if (detail instanceof Blob) {
        detail.text().then((t) => {
          try { msg = JSON.parse(t).detail } catch { msg = t }
          toast({ title: 'Fehler', description: msg, variant: 'destructive' })
        })
      } else {
        toast({ title: 'Fehler', description: detail?.detail ?? msg, variant: 'destructive' })
      }
    },
  })

  // ── DATEV Export ─────────────────────────────────────────────────────────────
  const datevExportMutation = useMutation({
    mutationFn: (data: any) => api.post('/payment-runs/datev', data),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['payment-runs'] })
      toast({ title: 'DATEV-Export erstellt' })
      handleDownload(res.data.id)
    },
    onError: (err: any) => {
      toast({ title: 'Fehler', description: err?.response?.data?.detail, variant: 'destructive' })
    },
  })

  async function handleDownload(runId: string) {
    try {
      const res = await api.get(`/payment-runs/${runId}/download`, { responseType: 'blob' })
      const contentDisposition = res.headers['content-disposition'] || ''
      const filenameMatch = contentDisposition.match(/filename="([^"]+)"/)
      const filename = filenameMatch?.[1] || `export_${runId}`
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast({ title: 'Fehler beim Download', variant: 'destructive' })
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Exporte</h1>
        <p className="text-sm text-slate-500 mt-1">SEPA-Zahlungen und DATEV-Buchungsstapel</p>
      </div>

      {/* ── SEPA Zahlungen ─────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Euro className="h-5 w-5" /> SEPA-Zahlungen
          </CardTitle>
          <CardDescription>
            Überweisungen für genehmigte Eingangsrechnungen (Kreditoren) und Mitarbeiter-Belege in einer pain.001-Datei.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">

          {/* Ausführungsdatum */}
          <div className="flex items-end gap-4">
            <div className="space-y-2">
              <Label>Ausführungsdatum</Label>
              <Input
                type="date"
                className="w-48"
                value={sepaExecDate}
                onChange={(e) => setSepaExecDate(e.target.value)}
              />
            </div>
            {totalCount > 0 && (
              <button className="text-sm text-slate-400 hover:text-slate-600" onClick={clearAll}>
                Auswahl zurücksetzen
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Eingangsrechnungen */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-medium text-sm">
                  <FileText className="h-4 w-4 text-slate-500" />
                  Eingangsrechnungen
                  <Badge variant="secondary">{payableInvoices.length}</Badge>
                </div>
                <button className="text-xs text-blue-600 hover:underline" onClick={selectAllInvoices}>
                  Alle wählen
                </button>
              </div>
              <div className="border rounded-md overflow-hidden">
                {payableInvoices.length === 0 ? (
                  <div className="p-4 text-center text-sm text-slate-400">
                    Keine genehmigten Eingangsrechnungen mit IBAN
                  </div>
                ) : (
                  <div className="max-h-64 overflow-y-auto divide-y">
                    {payableInvoices.map((inv) => (
                      <label
                        key={inv.id}
                        className="flex items-center gap-3 px-3 py-2.5 hover:bg-slate-50 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          className="h-4 w-4 shrink-0"
                          checked={selectedInvoiceIds.has(inv.id)}
                          onChange={() => toggleInvoice(inv.id)}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium truncate">{creditorName(inv.creditor)}</div>
                          <div className="text-xs text-slate-400 font-mono">{inv.document_number}</div>
                          {inv.due_date && (
                            <div className="text-xs text-slate-400">Fällig: {formatDate(inv.due_date)}</div>
                          )}
                        </div>
                        <div className="text-sm font-medium shrink-0">{formatCurrency(inv.total_gross)}</div>
                      </label>
                    ))}
                  </div>
                )}
              </div>
              {selectedInvoiceIds.size > 0 && (
                <div className="text-xs text-slate-500 text-right">
                  {selectedInvoiceIds.size} ausgewählt · {formatCurrency(invoicesTotal.toString())}
                </div>
              )}
            </div>

            {/* Mitarbeiter-Belege */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-medium text-sm">
                  <Users className="h-4 w-4 text-slate-500" />
                  Mitarbeiter-Belege
                  <Badge variant="secondary">{payableReceipts.length}</Badge>
                </div>
                <button className="text-xs text-blue-600 hover:underline" onClick={selectAllReceipts}>
                  Alle wählen
                </button>
              </div>
              <div className="border rounded-md overflow-hidden">
                {payableReceipts.length === 0 ? (
                  <div className="p-4 text-center text-sm text-slate-400">
                    Keine genehmigten Belege mit IBAN
                  </div>
                ) : (
                  <div className="max-h-64 overflow-y-auto divide-y">
                    {payableReceipts.map((r) => (
                      <label
                        key={r.id}
                        className="flex items-center gap-3 px-3 py-2.5 hover:bg-slate-50 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          className="h-4 w-4 shrink-0"
                          checked={selectedReceiptIds.has(r.id)}
                          onChange={() => toggleReceipt(r.id)}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium truncate">
                            {r.submitter?.full_name || '–'}
                          </div>
                          <div className="text-xs text-slate-400 font-mono">{r.receipt_number}</div>
                          <div className="text-xs text-slate-400 font-mono truncate">{r.reimbursement_iban}</div>
                        </div>
                        <div className="text-sm font-medium shrink-0">{formatCurrency(r.amount_gross)}</div>
                      </label>
                    ))}
                  </div>
                )}
              </div>
              {selectedReceiptIds.size > 0 && (
                <div className="text-xs text-slate-500 text-right">
                  {selectedReceiptIds.size} ausgewählt · {formatCurrency(receiptsTotal.toString())}
                </div>
              )}
            </div>
          </div>

          {/* Gesamtsumme + Export-Button */}
          <div className="flex items-center justify-between border-t pt-4">
            <div className="text-sm text-slate-600">
              {totalCount > 0 ? (
                <>
                  <span className="font-semibold">{totalCount} Position(en)</span> ausgewählt ·
                  Gesamtbetrag: <span className="font-semibold text-slate-900">{formatCurrency(grandTotal.toString())}</span>
                </>
              ) : (
                <span className="text-slate-400">Keine Positionen ausgewählt</span>
              )}
            </div>
            <Button
              disabled={totalCount === 0 || sepaExportMutation.isPending}
              onClick={() => sepaExportMutation.mutate()}
            >
              {sepaExportMutation.isPending
                ? <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                : <Download className="h-4 w-4 mr-2" />}
              SEPA-Datei erstellen
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* ── DATEV Export ───────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" /> DATEV-Export
          </CardTitle>
          <CardDescription>
            Erstellt einen DATEV Buchungsstapel (EXTF Format) für den angegebenen Zeitraum.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Zeitraum von *</Label>
              <Input type="date" value={datevFrom} onChange={(e) => setDatevFrom(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Zeitraum bis *</Label>
              <Input type="date" value={datevTo} onChange={(e) => setDatevTo(e.target.value)} />
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Es werden alle ausgestellten, versendeten und bezahlten Rechnungen im Zeitraum exportiert.
          </p>
          <Button
            disabled={!datevFrom || !datevTo || datevExportMutation.isPending}
            onClick={() => datevExportMutation.mutate({ period_from: datevFrom, period_to: datevTo })}
          >
            {datevExportMutation.isPending
              ? <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              : <Download className="h-4 w-4 mr-2" />}
            DATEV-CSV erstellen
          </Button>
        </CardContent>
      </Card>

      {/* ── Export-Verlauf ─────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Export-Verlauf</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Typ</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Positionen</TableHead>
                <TableHead>Betrag</TableHead>
                <TableHead>Erstellt am</TableHead>
                <TableHead>Download</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {runs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                    Noch keine Exporte vorhanden
                  </TableCell>
                </TableRow>
              ) : (
                runs.map((run) => (
                  <TableRow key={run.id}>
                    <TableCell className="text-sm">
                      {run.run_type === 'creditor_payment' ? 'SEPA Zahlung' :
                       run.run_type === 'sepa_export' ? 'SEPA' :
                       run.run_type === 'datev_export' ? 'DATEV' : 'Rechnungen'}
                    </TableCell>
                    <TableCell>
                      <Badge variant={run.status === 'completed' ? 'default' : run.status === 'failed' ? 'destructive' : 'secondary'}>
                        {run.status === 'completed' ? 'OK' : run.status === 'failed' ? 'Fehler' : run.status === 'running' ? 'Läuft' : 'Ausstehend'}
                      </Badge>
                    </TableCell>
                    <TableCell>{run.invoice_count ?? '–'}</TableCell>
                    <TableCell>{run.total_amount ? formatCurrency(run.total_amount) : '–'}</TableCell>
                    <TableCell>{formatDate(run.created_at)}</TableCell>
                    <TableCell>
                      {run.status === 'completed' && run.file_path && (
                        <Button variant="ghost" size="icon" onClick={() => handleDownload(run.id)}>
                          <Download className="h-4 w-4" />
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
