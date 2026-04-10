import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Download, Loader2, FileText, Building2 } from 'lucide-react'
import api from '@/lib/api'
import type { Invoice, PaymentRun } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { toast } from '@/hooks/use-toast'
import { formatDate, formatCurrency, INVOICE_STATUS_LABELS } from '@/lib/utils'

export function ExportsPage() {
  const queryClient = useQueryClient()
  const [selectedInvoiceIds, setSelectedInvoiceIds] = useState<Set<string>>(new Set())
  const [sepaExecDate, setSepaExecDate] = useState('')
  const [datevFrom, setDatevFrom] = useState('')
  const [datevTo, setDatevTo] = useState('')
  const [invoiceFilter, setInvoiceFilter] = useState('issued')

  const { data: invoicesData } = useQuery({
    queryKey: ['invoices', 'exports', invoiceFilter],
    queryFn: () =>
      api.get<Invoice[]>('/invoices', {
        params: {
          status: invoiceFilter !== 'all' ? invoiceFilter : undefined,
          page_size: 100,
        },
      }).then((r) => r.data),
  })

  const { data: runsData } = useQuery({
    queryKey: ['payment-runs', 'exports'],
    queryFn: () =>
      api.get<PaymentRun[]>('/payment-runs?page_size=20').then((r) => r.data),
  })

  const sepaExportMutation = useMutation({
    mutationFn: (data: any) => api.post('/payment-runs/sepa', data),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['payment-runs'] })
      toast({ title: 'SEPA-Export erstellt' })
      setSelectedInvoiceIds(new Set())
      // Auto-download
      handleDownload(res.data.id)
    },
    onError: (err: any) => {
      toast({ title: 'Fehler', description: err?.response?.data?.detail, variant: 'destructive' })
    },
  })

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

  const invoices = Array.isArray(invoicesData) ? invoicesData : []
  const runs = Array.isArray(runsData) ? runsData : []

  function toggleInvoice(id: string) {
    setSelectedInvoiceIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function selectAll() {
    setSelectedInvoiceIds(new Set(invoices.map((i) => i.id)))
  }

  function clearSelection() {
    setSelectedInvoiceIds(new Set())
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Exporte</h1>
        <p className="text-sm text-slate-500 mt-1">SEPA-Zahlungsdateien und DATEV-Buchungsstapel</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* SEPA Export */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="h-5 w-5" /> SEPA-Export
            </CardTitle>
            <CardDescription>
              Erstellt eine SEPA pain.001.003.03 Zahlungsdatei für die ausgewählten Rechnungen.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Ausführungsdatum</Label>
              <Input
                type="date"
                value={sepaExecDate}
                onChange={(e) => setSepaExecDate(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Rechnungen auswählen</Label>
                <div className="flex gap-2 text-xs">
                  <button className="text-blue-600 hover:underline" onClick={selectAll}>Alle</button>
                  <span className="text-muted-foreground">|</span>
                  <button className="text-blue-600 hover:underline" onClick={clearSelection}>Keine</button>
                </div>
              </div>
              <div className="flex gap-1 mb-2">
                {['all', 'issued', 'sent'].map((s) => (
                  <Button
                    key={s}
                    variant={invoiceFilter === s ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => { setInvoiceFilter(s); setSelectedInvoiceIds(new Set()) }}
                  >
                    {s === 'all' ? 'Alle' : INVOICE_STATUS_LABELS[s]}
                  </Button>
                ))}
              </div>
              <div className="border rounded-md max-h-56 overflow-y-auto">
                {invoices.length === 0 ? (
                  <div className="p-4 text-center text-sm text-muted-foreground">Keine Rechnungen</div>
                ) : (
                  invoices.map((inv) => (
                    <label
                      key={inv.id}
                      className="flex items-center gap-3 px-3 py-2 hover:bg-accent cursor-pointer border-b last:border-0"
                    >
                      <input
                        type="checkbox"
                        checked={selectedInvoiceIds.has(inv.id)}
                        onChange={() => toggleInvoice(inv.id)}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="font-mono text-sm">{inv.invoice_number}</div>
                        <div className="text-xs text-muted-foreground">{formatDate(inv.invoice_date)}</div>
                      </div>
                      <div className="text-sm font-medium">{formatCurrency(inv.total_gross)}</div>
                    </label>
                  ))
                )}
              </div>
              <div className="text-sm text-muted-foreground">
                {selectedInvoiceIds.size} ausgewählt –{' '}
                {formatCurrency(
                  invoices
                    .filter((i) => selectedInvoiceIds.has(i.id))
                    .reduce((s, i) => s + parseFloat(i.total_gross), 0)
                )}
              </div>
            </div>

            <Button
              className="w-full"
              disabled={selectedInvoiceIds.size === 0 || sepaExportMutation.isPending}
              onClick={() =>
                sepaExportMutation.mutate({
                  invoice_ids: Array.from(selectedInvoiceIds),
                  execution_date: sepaExecDate || undefined,
                })
              }
            >
              {sepaExportMutation.isPending ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Download className="h-4 w-4 mr-2" />
              )}
              SEPA-Datei erstellen
            </Button>
          </CardContent>
        </Card>

        {/* DATEV Export */}
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
                <Input
                  type="date"
                  value={datevFrom}
                  onChange={(e) => setDatevFrom(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Zeitraum bis *</Label>
                <Input
                  type="date"
                  value={datevTo}
                  onChange={(e) => setDatevTo(e.target.value)}
                />
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              Es werden alle ausgestellten, versendeten und bezahlten Rechnungen im Zeitraum exportiert.
            </p>
            <Button
              className="w-full"
              disabled={!datevFrom || !datevTo || datevExportMutation.isPending}
              onClick={() =>
                datevExportMutation.mutate({
                  period_from: datevFrom,
                  period_to: datevTo,
                })
              }
            >
              {datevExportMutation.isPending ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Download className="h-4 w-4 mr-2" />
              )}
              DATEV-CSV erstellen
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Export History */}
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
                <TableHead>Zeitraum</TableHead>
                <TableHead>Rechnungen</TableHead>
                <TableHead>Betrag</TableHead>
                <TableHead>Erstellt am</TableHead>
                <TableHead>Download</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {runs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                    Noch keine Exporte vorhanden
                  </TableCell>
                </TableRow>
              ) : (
                runs.map((run) => (
                  <TableRow key={run.id}>
                    <TableCell className="text-sm">
                      {run.run_type === 'sepa_export' ? 'SEPA' :
                       run.run_type === 'datev_export' ? 'DATEV' : 'Rechnungen'}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          run.status === 'completed' ? 'default' :
                          run.status === 'failed' ? 'destructive' : 'secondary'
                        }
                      >
                        {run.status === 'completed' ? 'OK' :
                         run.status === 'failed' ? 'Fehler' :
                         run.status === 'running' ? 'Läuft' : 'Ausstehend'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm">
                      {run.period_from
                        ? `${formatDate(run.period_from)} – ${formatDate(run.period_to)}`
                        : '–'}
                    </TableCell>
                    <TableCell>{run.invoice_count ?? '–'}</TableCell>
                    <TableCell>{run.total_amount ? formatCurrency(run.total_amount) : '–'}</TableCell>
                    <TableCell>{formatDate(run.created_at)}</TableCell>
                    <TableCell>
                      {run.status === 'completed' && run.file_path && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDownload(run.id)}
                        >
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
