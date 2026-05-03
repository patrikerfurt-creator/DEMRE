import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Play, Search, Loader2, Download } from 'lucide-react'
import api from '@/lib/api'
import type { Invoice } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { toast } from '@/hooks/use-toast'
import { formatDate, formatCurrency, INVOICE_STATUS_LABELS, INVOICE_STATUS_COLORS } from '@/lib/utils'

export function InvoiceListPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState('all')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [generateOpen, setGenerateOpen] = useState(false)
  const [genPeriodFrom, setGenPeriodFrom] = useState('')
  const [genPeriodTo, setGenPeriodTo] = useState('')
  const [genAutoIssue, setGenAutoIssue] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['invoices', statusFilter, dateFrom, dateTo, search, page],
    queryFn: () =>
      api.get<Invoice[]>('/invoices', {
        params: {
          status: statusFilter !== 'all' ? statusFilter : undefined,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
          search: search || undefined,
          page,
          page_size: 25,
        },
      }).then((r) => r.data),
  })

  const generateMutation = useMutation({
    mutationFn: (payload: any) => api.post('/invoices/generate', payload),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
      setGenerateOpen(false)
      toast({ title: `${res.data.length} Rechnungen erstellt` })
    },
    onError: (err: any) => {
      toast({ title: 'Fehler', description: err?.response?.data?.detail, variant: 'destructive' })
    },
  })

  function handleGenerate(e: React.FormEvent) {
    e.preventDefault()
    if (!genPeriodFrom || !genPeriodTo) {
      toast({ title: 'Fehler', description: 'Zeitraum erforderlich', variant: 'destructive' })
      return
    }
    generateMutation.mutate({
      period_from: genPeriodFrom,
      period_to: genPeriodTo,
      auto_issue: genAutoIssue,
    })
  }

  const invoices = Array.isArray(data) ? data : []

  const statuses = ['all', 'draft', 'issued', 'sent', 'paid', 'overdue', 'cancelled']

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Rechnungen</h1>
          <p className="text-sm text-slate-500 mt-1">{invoices.length} Rechnungen</p>
        </div>
        <Button onClick={() => setGenerateOpen(true)}>
          <Play className="h-4 w-4 mr-2" /> Rechnungen erzeugen
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex gap-1 flex-wrap">
          {statuses.map((s) => (
            <Button
              key={s}
              variant={statusFilter === s ? 'default' : 'outline'}
              size="sm"
              onClick={() => { setStatusFilter(s); setPage(1) }}
            >
              {s === 'all' ? 'Alle' : INVOICE_STATUS_LABELS[s]}
            </Button>
          ))}
        </div>
        <div className="flex items-center gap-2 ml-auto">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
            <Input
              className="pl-8 w-56"
              placeholder="Nummer, Kunde..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1) }}
            />
          </div>
          <Label className="text-sm">Von</Label>
          <Input type="date" className="w-36" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          <Label className="text-sm">Bis</Label>
          <Input type="date" className="w-36" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </div>
      </div>

      <div className="border rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nummer</TableHead>
              <TableHead>Datum</TableHead>
              <TableHead>Fällig</TableHead>
              <TableHead>Leistungszeitraum</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Netto</TableHead>
              <TableHead className="text-right">MwSt.</TableHead>
              <TableHead className="text-right">Brutto</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center py-12">
                  <Loader2 className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
                </TableCell>
              </TableRow>
            ) : invoices.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center text-muted-foreground py-12">
                  Keine Rechnungen gefunden
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
                  <TableCell className="text-xs text-muted-foreground">
                    {inv.billing_period_from
                      ? `${formatDate(inv.billing_period_from)} – ${formatDate(inv.billing_period_to)}`
                      : '–'}
                  </TableCell>
                  <TableCell>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${INVOICE_STATUS_COLORS[inv.status]}`}>
                      {INVOICE_STATUS_LABELS[inv.status]}
                    </span>
                  </TableCell>
                  <TableCell className="text-right text-sm">{formatCurrency(inv.subtotal_net)}</TableCell>
                  <TableCell className="text-right text-sm">{formatCurrency(inv.total_vat)}</TableCell>
                  <TableCell className="text-right font-medium">{formatCurrency(inv.total_gross)}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <div className="flex justify-center gap-2">
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
          Zurück
        </Button>
        <span className="py-2 px-3 text-sm">Seite {page}</span>
        <Button variant="outline" size="sm" disabled={invoices.length < 25} onClick={() => setPage(p => p + 1)}>
          Weiter
        </Button>
      </div>

      {/* Generate Dialog */}
      <Dialog open={generateOpen} onOpenChange={setGenerateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rechnungen erzeugen</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleGenerate} className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Erstellt Rechnungen für alle aktiven Verträge im angegebenen Zeitraum.
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Zeitraum von *</Label>
                <Input
                  type="date"
                  value={genPeriodFrom}
                  onChange={(e) => setGenPeriodFrom(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>Zeitraum bis *</Label>
                <Input
                  type="date"
                  value={genPeriodTo}
                  onChange={(e) => setGenPeriodTo(e.target.value)}
                  required
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="auto-issue"
                checked={genAutoIssue}
                onChange={(e) => setGenAutoIssue(e.target.checked)}
              />
              <Label htmlFor="auto-issue">Rechnungen direkt ausstellen (Status: Ausgestellt)</Label>
            </div>
            <DialogFooter>
              <Button variant="outline" type="button" onClick={() => setGenerateOpen(false)}>Abbrechen</Button>
              <Button type="submit" disabled={generateMutation.isPending}>
                {generateMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Rechnungen erstellen
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
