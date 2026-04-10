import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Building2, Phone, Mail, CreditCard } from 'lucide-react'
import api from '@/lib/api'
import type { Customer, Contract, Invoice } from '@/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { formatDate, formatCurrency, INVOICE_STATUS_LABELS, INVOICE_STATUS_COLORS, CONTRACT_STATUS_LABELS } from '@/lib/utils'

export function CustomerDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()

  const { data: customer, isLoading } = useQuery({
    queryKey: ['customer', id],
    queryFn: () => api.get<Customer>(`/customers/${id}`).then((r) => r.data),
    enabled: !!id,
  })

  const { data: contracts } = useQuery({
    queryKey: ['contracts', 'customer', id],
    queryFn: () => api.get<Contract[]>(`/contracts?customer_id=${id}&page_size=100`).then((r) => r.data),
    enabled: !!id,
  })

  const { data: invoices } = useQuery({
    queryKey: ['invoices', 'customer', id],
    queryFn: () => api.get<Invoice[]>(`/invoices?customer_id=${id}&page_size=100`).then((r) => r.data),
    enabled: !!id,
  })

  if (isLoading) {
    return <div className="p-6 text-muted-foreground">Lädt...</div>
  }
  if (!customer) {
    return <div className="p-6 text-muted-foreground">Kunde nicht gefunden</div>
  }

  const displayName = customer.company_name
    || `${customer.first_name || ''} ${customer.last_name || ''}`.trim()
    || customer.customer_number

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/customers')}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{displayName}</h1>
          <p className="text-sm text-slate-500">Kundennummer: {customer.customer_number}</p>
        </div>
        <Badge variant={customer.is_active ? 'default' : 'secondary'} className="ml-auto">
          {customer.is_active ? 'Aktiv' : 'Inaktiv'}
        </Badge>
      </div>

      {/* Customer Info */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Building2 className="h-4 w-4" /> Adresse
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm space-y-1">
            {customer.company_name && <div className="font-medium">{customer.company_name}</div>}
            {(customer.first_name || customer.last_name) && (
              <div>{[customer.salutation, customer.first_name, customer.last_name].filter(Boolean).join(' ')}</div>
            )}
            {customer.address_line1 && <div>{customer.address_line1}</div>}
            {customer.address_line2 && <div>{customer.address_line2}</div>}
            {(customer.postal_code || customer.city) && (
              <div>{[customer.postal_code, customer.city].filter(Boolean).join(' ')}</div>
            )}
            <div className="text-muted-foreground">{customer.country_code}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Phone className="h-4 w-4" /> Kontakt
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm space-y-1">
            {customer.email && <div className="flex items-center gap-2"><Mail className="h-3 w-3" />{customer.email}</div>}
            {customer.phone && <div className="flex items-center gap-2"><Phone className="h-3 w-3" />{customer.phone}</div>}
            {customer.vat_id && <div>USt-IdNr.: {customer.vat_id}</div>}
            {customer.tax_number && <div>Steuernummer: {customer.tax_number}</div>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <CreditCard className="h-4 w-4" /> Bankverbindung
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm space-y-1">
            {customer.bank_name && <div className="font-medium">{customer.bank_name}</div>}
            {customer.account_holder && <div>{customer.account_holder}</div>}
            {customer.iban && <div className="font-mono">{customer.iban}</div>}
            {customer.bic && <div className="font-mono">{customer.bic}</div>}
            {customer.datev_account_number && (
              <div className="text-muted-foreground">DATEV: {customer.datev_account_number}</div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="contracts">
        <TabsList>
          <TabsTrigger value="contracts">
            Verträge ({Array.isArray(contracts) ? contracts.length : 0})
          </TabsTrigger>
          <TabsTrigger value="invoices">
            Rechnungen ({Array.isArray(invoices) ? invoices.length : 0})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="contracts">
          <div className="border rounded-lg mt-2">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Vertragsnummer</TableHead>
                  <TableHead>Objekt</TableHead>
                  <TableHead>Start</TableHead>
                  <TableHead>Ende</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Positionen</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {!Array.isArray(contracts) || contracts.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                      Keine Verträge vorhanden
                    </TableCell>
                  </TableRow>
                ) : (
                  contracts.map((c) => (
                    <TableRow
                      key={c.id}
                      className="cursor-pointer"
                      onClick={() => navigate(`/contracts/${c.id}`)}
                    >
                      <TableCell className="font-mono text-sm">{c.contract_number}</TableCell>
                      <TableCell>{c.property_ref || '–'}</TableCell>
                      <TableCell>{formatDate(c.start_date)}</TableCell>
                      <TableCell>{formatDate(c.end_date)}</TableCell>
                      <TableCell>
                        <Badge variant={c.status === 'active' ? 'default' : 'secondary'}>
                          {CONTRACT_STATUS_LABELS[c.status]}
                        </Badge>
                      </TableCell>
                      <TableCell>{c.items.length}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        <TabsContent value="invoices">
          <div className="border rounded-lg mt-2">
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
                {!Array.isArray(invoices) || invoices.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                      Keine Rechnungen vorhanden
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
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
