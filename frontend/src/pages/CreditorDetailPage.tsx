import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Building2, Phone, CreditCard, FileText } from 'lucide-react'
import api from '@/lib/api'
import type { Creditor, IncomingInvoice, IncomingInvoiceListResponse } from '@/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { formatDate, formatCurrency } from '@/lib/utils'

const INCOMING_STATUS_LABELS: Record<string, string> = {
  open: 'Offen',
  approved: 'Freigegeben',
  scheduled: 'Geplant',
  paid: 'Bezahlt',
  rejected: 'Abgelehnt',
  cancelled: 'Storniert',
}

const INCOMING_STATUS_COLORS: Record<string, string> = {
  open: 'bg-yellow-100 text-yellow-800',
  approved: 'bg-blue-100 text-blue-800',
  scheduled: 'bg-indigo-100 text-indigo-800',
  paid: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-700',
}

export function CreditorDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()

  const { data: creditor, isLoading } = useQuery({
    queryKey: ['creditor', id],
    queryFn: () => api.get<Creditor>(`/creditors/${id}`).then((r) => r.data),
    enabled: !!id,
  })

  const { data: invoicesData } = useQuery({
    queryKey: ['incoming-invoices', 'creditor', id],
    queryFn: () =>
      api.get<IncomingInvoiceListResponse>('/incoming-invoices', {
        params: { creditor_id: id, page_size: 100 },
      }).then((r) => r.data),
    enabled: !!id,
  })

  if (isLoading) return <div className="p-6 text-muted-foreground">Lädt...</div>
  if (!creditor) return <div className="p-6 text-muted-foreground">Kreditor nicht gefunden</div>

  const displayName =
    creditor.company_name ||
    [creditor.first_name, creditor.last_name].filter(Boolean).join(' ') ||
    creditor.creditor_number

  const invoices: IncomingInvoice[] = invoicesData?.items ?? []
  const totalOpen = invoices
    .filter((i) => ['open', 'approved', 'scheduled'].includes(i.status))
    .reduce((sum, i) => sum + parseFloat(i.total_gross as unknown as string), 0)

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/creditors')}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{displayName}</h1>
          <p className="text-sm text-slate-500">Kreditoren-Nr.: {creditor.creditor_number}</p>
        </div>
        <Badge variant={creditor.is_active ? 'default' : 'secondary'} className="ml-auto">
          {creditor.is_active ? 'Aktiv' : 'Inaktiv'}
        </Badge>
      </div>

      {/* Info-Karten */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Building2 className="h-4 w-4" /> Adresse
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm space-y-1">
            {creditor.company_name && <div className="font-medium">{creditor.company_name}</div>}
            {(creditor.first_name || creditor.last_name) && (
              <div>{[creditor.first_name, creditor.last_name].filter(Boolean).join(' ')}</div>
            )}
            {creditor.address_line1 && <div>{creditor.address_line1}</div>}
            {creditor.address_line2 && <div>{creditor.address_line2}</div>}
            {(creditor.postal_code || creditor.city) && (
              <div>{[creditor.postal_code, creditor.city].filter(Boolean).join(' ')}</div>
            )}
            <div className="text-muted-foreground">{creditor.country_code}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Phone className="h-4 w-4" /> Kontakt & Steuer
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm space-y-1">
            {creditor.email && <div>{creditor.email}</div>}
            {creditor.phone && <div>{creditor.phone}</div>}
            {creditor.vat_id && <div>USt-IdNr.: {creditor.vat_id}</div>}
            {creditor.tax_number && <div>Steuernr.: {creditor.tax_number}</div>}
            {creditor.datev_account_number && (
              <div className="text-muted-foreground">DATEV: {creditor.datev_account_number}</div>
            )}
            <div className="text-muted-foreground">Zahlungsziel: {creditor.payment_terms_days} Tage</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <CreditCard className="h-4 w-4" /> Bankverbindung
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm space-y-1">
            {creditor.bank_name && <div className="font-medium">{creditor.bank_name}</div>}
            {creditor.account_holder && <div>{creditor.account_holder}</div>}
            {creditor.iban && <div className="font-mono">{creditor.iban}</div>}
            {creditor.bic && <div className="font-mono text-muted-foreground">{creditor.bic}</div>}
            {!creditor.iban && !creditor.bic && (
              <div className="text-muted-foreground">Keine Bankverbindung hinterlegt</div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Eingangsrechnungen */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Eingangsrechnungen ({invoices.length})
          </h2>
          {totalOpen > 0 && (
            <div className="text-sm text-muted-foreground">
              Offen: <span className="font-semibold text-slate-800">{formatCurrency(totalOpen)}</span>
            </div>
          )}
        </div>

        <div className="border rounded-lg">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Dok.-Nr.</TableHead>
                <TableHead>Ext. Rechnungsnr.</TableHead>
                <TableHead>Datum</TableHead>
                <TableHead>Fällig</TableHead>
                <TableHead>Beschreibung</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Brutto</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {invoices.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground py-10">
                    Keine Eingangsrechnungen vorhanden
                  </TableCell>
                </TableRow>
              ) : (
                invoices.map((inv) => (
                  <TableRow
                    key={inv.id}
                    className="cursor-pointer hover:bg-slate-50"
                    onClick={() => navigate(`/incoming-invoices?creditor_id=${id}`)}
                  >
                    <TableCell className="font-mono text-sm">{inv.document_number}</TableCell>
                    <TableCell className="text-sm">{inv.external_invoice_number || '–'}</TableCell>
                    <TableCell>{formatDate(inv.invoice_date)}</TableCell>
                    <TableCell>{inv.due_date ? formatDate(inv.due_date) : '–'}</TableCell>
                    <TableCell className="max-w-xs truncate text-sm text-muted-foreground">
                      {inv.description || '–'}
                    </TableCell>
                    <TableCell>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${INCOMING_STATUS_COLORS[inv.status] ?? ''}`}>
                        {INCOMING_STATUS_LABELS[inv.status] ?? inv.status}
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
        </div>
      </div>
    </div>
  )
}
