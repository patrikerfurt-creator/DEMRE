import { useQuery } from '@tanstack/react-query'
import { TrendingUp, FileText, AlertTriangle, CheckCircle, Clock } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import api from '@/lib/api'
import { formatCurrency, formatDate, INVOICE_STATUS_LABELS, INVOICE_STATUS_COLORS } from '@/lib/utils'
import type { Invoice, PaymentRun } from '@/types'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const STATUS_COLORS_CHART: Record<string, string> = {
  draft: '#94a3b8',
  issued: '#3b82f6',
  sent: '#6366f1',
  paid: '#22c55e',
  overdue: '#ef4444',
  cancelled: '#f97316',
}

export function DashboardPage() {
  const { data: invoicesData } = useQuery({
    queryKey: ['invoices', 'dashboard'],
    queryFn: () => api.get<Invoice[]>('/invoices?page_size=100').then((r) => r.data),
  })

  const { data: runsData } = useQuery({
    queryKey: ['payment-runs', 'dashboard'],
    queryFn: () => api.get<PaymentRun[]>('/payment-runs?page_size=5').then((r) => r.data),
  })

  const invoices = Array.isArray(invoicesData) ? invoicesData : []
  const recentInvoices = [...invoices].slice(0, 10)

  // Stats
  const openAmount = invoices
    .filter((i) => ['issued', 'sent', 'overdue'].includes(i.status))
    .reduce((s, i) => s + parseFloat(i.total_gross), 0)

  const overdueCount = invoices.filter((i) => i.status === 'overdue').length
  const paidCount = invoices.filter((i) => i.status === 'paid').length
  const draftCount = invoices.filter((i) => i.status === 'draft').length

  // Chart data
  const statusGroups = invoices.reduce<Record<string, number>>((acc, inv) => {
    acc[inv.status] = (acc[inv.status] || 0) + 1
    return acc
  }, {})

  const chartData = Object.entries(statusGroups).map(([status, count]) => ({
    name: INVOICE_STATUS_LABELS[status] || status,
    count,
    status,
  }))

  const lastRun = Array.isArray(runsData) ? runsData[0] : undefined

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
        <p className="text-sm text-slate-500 mt-1">Übersicht der Abrechnungsaktivitäten</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Offene Forderungen</p>
                <p className="text-2xl font-bold text-blue-600">{formatCurrency(openAmount)}</p>
              </div>
              <TrendingUp className="h-8 w-8 text-blue-400" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Überfällig</p>
                <p className="text-2xl font-bold text-red-600">{overdueCount}</p>
              </div>
              <AlertTriangle className="h-8 w-8 text-red-400" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Bezahlt</p>
                <p className="text-2xl font-bold text-green-600">{paidCount}</p>
              </div>
              <CheckCircle className="h-8 w-8 text-green-400" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Entwürfe</p>
                <p className="text-2xl font-bold text-slate-600">{draftCount}</p>
              </div>
              <FileText className="h-8 w-8 text-slate-400" />
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Chart */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Rechnungen nach Status</CardTitle>
          </CardHeader>
          <CardContent>
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={chartData}>
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip
                    formatter={(value: number) => [value, 'Anzahl']}
                  />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {chartData.map((entry) => (
                      <Cell
                        key={entry.status}
                        fill={STATUS_COLORS_CHART[entry.status] || '#94a3b8'}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[200px] flex items-center justify-center text-muted-foreground text-sm">
                Keine Daten verfügbar
              </div>
            )}
          </CardContent>
        </Card>

        {/* Next run info */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Letzter Abrechnungslauf</CardTitle>
          </CardHeader>
          <CardContent>
            {lastRun ? (
              <div className="space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Typ</span>
                  <span className="font-medium">
                    {lastRun.run_type === 'invoice_generation' ? 'Rechnungsstellung' :
                     lastRun.run_type === 'sepa_export' ? 'SEPA-Export' : 'DATEV-Export'}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Status</span>
                  <Badge variant={lastRun.status === 'completed' ? 'default' : 'destructive'}>
                    {lastRun.status === 'completed' ? 'Abgeschlossen' :
                     lastRun.status === 'running' ? 'Läuft' :
                     lastRun.status === 'failed' ? 'Fehler' : 'Ausstehend'}
                  </Badge>
                </div>
                {lastRun.period_from && (
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Zeitraum</span>
                    <span>{formatDate(lastRun.period_from)} – {formatDate(lastRun.period_to)}</span>
                  </div>
                )}
                {lastRun.invoice_count !== undefined && (
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Rechnungen</span>
                    <span className="font-medium">{lastRun.invoice_count}</span>
                  </div>
                )}
                {lastRun.total_amount && (
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Gesamtbetrag</span>
                    <span className="font-medium">{formatCurrency(lastRun.total_amount)}</span>
                  </div>
                )}
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Erstellt am</span>
                  <span>{formatDate(lastRun.created_at)}</span>
                </div>
                <div className="mt-4 p-3 bg-blue-50 rounded-md flex items-center gap-2 text-sm text-blue-700">
                  <Clock className="h-4 w-4" />
                  Nächster automatischer Lauf: 1. des nächsten Monats um 02:00 Uhr
                </div>
              </div>
            ) : (
              <div className="text-center text-muted-foreground text-sm py-8">
                Noch keine Abrechnungsläufe vorhanden
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Invoices */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Letzte Rechnungen</CardTitle>
        </CardHeader>
        <CardContent>
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
              {recentInvoices.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                    Keine Rechnungen vorhanden
                  </TableCell>
                </TableRow>
              ) : (
                recentInvoices.map((inv) => (
                  <TableRow key={inv.id}>
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
        </CardContent>
      </Card>
    </div>
  )
}
