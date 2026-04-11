import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Plus, Trash2, Loader2, ChevronLeft, Search, X, ChevronRight } from 'lucide-react'
import api from '@/lib/api'
import type { Customer, Article, CustomerListResponse } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/hooks/use-toast'
import { formatCurrency, cn } from '@/lib/utils'

// ── Helpers ────────────────────────────────────────────────────────────────────

function customerDisplayName(c: Customer): string {
  if (c.company_name) return c.company_name
  return [c.salutation, c.first_name, c.last_name].filter(Boolean).join(' ')
}

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

function addDays(dateStr: string, days: number): string {
  const d = new Date(dateStr)
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

// ── Types ──────────────────────────────────────────────────────────────────────

interface LineItem {
  _key: string
  article_id: string
  article_name: string
  description: string
  quantity: string
  unit: string
  unit_price_net: string
  vat_rate: string
}

function calcItem(item: LineItem) {
  const qty = parseFloat(item.quantity) || 0
  const price = parseFloat(item.unit_price_net) || 0
  const vat = parseFloat(item.vat_rate) || 0
  const net = qty * price
  const vatAmt = net * (vat / 100)
  return { net, vatAmt, gross: net + vatAmt }
}

function generateKey(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2)
}

function newItem(): LineItem {
  return {
    _key: generateKey(),
    article_id: '',
    article_name: '',
    description: '',
    quantity: '',
    unit: '',
    unit_price_net: '',
    vat_rate: '',
  }
}

// ── Searchable Customer Picker ─────────────────────────────────────────────────

function CustomerPicker({
  value,
  onChange,
}: {
  value: Customer | null
  onChange: (c: Customer | null) => void
}) {
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const { data } = useQuery({
    queryKey: ['customers-search', search],
    queryFn: () =>
      api
        .get<CustomerListResponse>('/customers', {
          params: { search: search || undefined, is_active: true, page_size: 20 },
        })
        .then((r) => r.data),
    enabled: open,
  })

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  const customers = data?.items ?? []

  if (value) {
    return (
      <div className="flex items-center gap-2 p-3 border rounded-lg bg-blue-50 border-blue-200">
        <div className="flex-1">
          <div className="font-medium text-sm">{customerDisplayName(value)}</div>
          <div className="text-xs text-slate-500">{value.customer_number} · {value.city}</div>
        </div>
        <Button variant="outline" size="sm" onClick={() => onChange(null)}>
          Ändern
        </Button>
      </div>
    )
  }

  return (
    <div ref={ref} className="relative">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
        <Input
          className="pl-9"
          placeholder="Kunde suchen..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onFocus={() => setOpen(true)}
        />
      </div>
      {open && (
        <div className="absolute z-50 mt-1 w-full bg-white border rounded-lg shadow-lg max-h-60 overflow-y-auto">
          {customers.length === 0 ? (
            <div className="px-4 py-3 text-sm text-slate-500">Keine Kunden gefunden</div>
          ) : (
            customers.map((c) => (
              <button
                key={c.id}
                type="button"
                className="w-full text-left px-4 py-2.5 hover:bg-slate-50 text-sm"
                onMouseDown={() => {
                  onChange(c)
                  setOpen(false)
                  setSearch('')
                }}
              >
                <div className="font-medium">{customerDisplayName(c)}</div>
                <div className="text-xs text-slate-400">{c.customer_number} · {c.city}</div>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}

// ── Article Side Drawer ────────────────────────────────────────────────────────

function ArticleDrawer({
  open,
  onClose,
  onSelect,
}: {
  open: boolean
  onClose: () => void
  onSelect: (a: Article) => void
}) {
  const [search, setSearch] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['articles-drawer', search],
    queryFn: () =>
      api
        .get<Article[]>('/articles', {
          params: { search: search || undefined, is_active: true, page_size: 200 },
        })
        .then((r) => r.data),
    enabled: open,
  })

  // Reset search when drawer closes
  useEffect(() => {
    if (!open) setSearch('')
  }, [open])

  // Close on Escape
  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  const articles = Array.isArray(data) ? data : []

  return (
    <>
      {/* Overlay */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/30"
          onClick={onClose}
        />
      )}

      {/* Side Panel */}
      <div
        className={cn(
          'fixed top-0 right-0 z-50 h-full w-96 bg-white shadow-2xl flex flex-col transition-transform duration-300 ease-in-out',
          open ? 'translate-x-0' : 'translate-x-full'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b bg-slate-50">
          <h3 className="font-semibold text-slate-800">Artikel auswählen</h3>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Search */}
        <div className="px-4 py-3 border-b">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <Input
              className="pl-9"
              placeholder="Artikel suchen..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              autoFocus
            />
          </div>
        </div>

        {/* Article List */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
            </div>
          ) : articles.length === 0 ? (
            <div className="px-5 py-8 text-center text-sm text-slate-400">
              Keine Artikel gefunden
            </div>
          ) : (
            <ul className="divide-y">
              {articles.map((a) => (
                <li key={a.id}>
                  <button
                    type="button"
                    className="w-full text-left px-5 py-3.5 hover:bg-blue-50 transition-colors flex items-center gap-3 group"
                    onClick={() => {
                      onSelect(a)
                      onClose()
                    }}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-sm text-slate-800 truncate">{a.name}</div>
                      <div className="text-xs text-slate-400 mt-0.5 flex items-center gap-2">
                        <span>{a.article_number}</span>
                        <span>·</span>
                        <span>{parseFloat(a.unit_price).toFixed(2)} €{a.unit ? ` / ${a.unit}` : ''}</span>
                        <span>·</span>
                        <span>{parseFloat(a.vat_rate).toFixed(0)} % MwSt.</span>
                      </div>
                      {a.description && (
                        <div className="text-xs text-slate-400 mt-0.5 truncate">{a.description}</div>
                      )}
                    </div>
                    <ChevronRight className="h-4 w-4 text-slate-300 group-hover:text-blue-400 flex-shrink-0" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t bg-slate-50 text-xs text-slate-400">
          {articles.length > 0 && `${articles.length} Artikel`}
        </div>
      </div>
    </>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export function InvoiceCreatePage() {
  const navigate = useNavigate()

  const [customer, setCustomer] = useState<Customer | null>(null)
  const [invoiceDate, setInvoiceDate] = useState(today())
  const [dueDate, setDueDate] = useState(addDays(today(), 14))
  const [periodFrom, setPeriodFrom] = useState('')
  const [periodTo, setPeriodTo] = useState('')
  const [notes, setNotes] = useState('')
  const [items, setItems] = useState<LineItem[]>([newItem()])
  const [drawerKey, setDrawerKey] = useState<string | null>(null)

  // Update due date when invoice date changes
  const handleInvoiceDateChange = useCallback((val: string) => {
    setInvoiceDate(val)
    if (val) setDueDate(addDays(val, 14))
  }, [])

  function updateItem(key: string, field: keyof LineItem, value: string) {
    setItems((prev) =>
      prev.map((it) => (it._key === key ? { ...it, [field]: value } : it))
    )
  }

  function removeItem(key: string) {
    setItems((prev) => prev.filter((it) => it._key !== key))
  }

  function applyArticle(key: string, article: Article) {
    setItems((prev) =>
      prev.map((it) =>
        it._key === key
          ? {
              ...it,
              article_id: article.id,
              article_name: article.name,
              description: article.name,
              unit: article.unit ?? '',
              unit_price_net: parseFloat(article.unit_price).toString(),
              vat_rate: parseFloat(article.vat_rate).toString(),
            }
          : it
      )
    )
  }

  // Totals
  const totals = items.reduce(
    (acc, it) => {
      const { net, vatAmt, gross } = calcItem(it)
      return { net: acc.net + net, vat: acc.vat + vatAmt, gross: acc.gross + gross }
    },
    { net: 0, vat: 0, gross: 0 }
  )

  const createMutation = useMutation({
    mutationFn: (payload: unknown) => api.post('/invoices', payload),
    onSuccess: (res) => {
      toast({ title: 'Rechnung erstellt', description: res.data.invoice_number })
      navigate(`/invoices/${res.data.id}`)
    },
    onError: (err: any) => {
      toast({
        title: 'Fehler',
        description: err?.response?.data?.detail ?? 'Unbekannter Fehler',
        variant: 'destructive',
      })
    },
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    if (!customer) {
      toast({ title: 'Fehler', description: 'Bitte Kunden auswählen', variant: 'destructive' })
      return
    }
    if (items.length === 0) {
      toast({ title: 'Fehler', description: 'Mindestens eine Position erforderlich', variant: 'destructive' })
      return
    }
    for (const it of items) {
      if (!it.description.trim()) {
        toast({ title: 'Fehler', description: 'Alle Positionen müssen eine Beschreibung haben', variant: 'destructive' })
        return
      }
      if (!it.unit_price_net) {
        toast({ title: 'Fehler', description: 'Alle Positionen müssen einen Preis haben', variant: 'destructive' })
        return
      }
    }

    const payload = {
      customer_id: customer.id,
      invoice_date: invoiceDate,
      due_date: dueDate,
      billing_period_from: periodFrom || null,
      billing_period_to: periodTo || null,
      notes: notes || null,
      status: 'draft',
      items: items.map((it, idx) => {
        const { net, vatAmt, gross } = calcItem(it)
        return {
          position: idx + 1,
          article_id: it.article_id || null,
          description: it.description,
          quantity: parseFloat(it.quantity) || 1,
          unit: it.unit || null,
          unit_price_net: parseFloat(it.unit_price_net) || 0,
          vat_rate: parseFloat(it.vat_rate) || 0,
          total_net: Math.round(net * 10000) / 10000,
          total_vat: Math.round(vatAmt * 10000) / 10000,
          total_gross: Math.round(gross * 10000) / 10000,
        }
      }),
    }

    createMutation.mutate(payload)
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Article Drawer */}
      <ArticleDrawer
        open={drawerKey !== null}
        onClose={() => setDrawerKey(null)}
        onSelect={(a) => {
          if (drawerKey) applyArticle(drawerKey, a)
          setDrawerKey(null)
        }}
      />

      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate('/invoices')}>
          <ChevronLeft className="h-4 w-4 mr-1" /> Zurück
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-slate-900">Rechnung erstellen</h1>
          <p className="text-sm text-slate-500 mt-0.5">Manuelle Rechnung – wird als Entwurf gespeichert</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate('/invoices')}>
            Abbrechen
          </Button>
          <Button onClick={handleSubmit} disabled={createMutation.isPending}>
            {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Rechnung speichern
          </Button>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Kunde */}
        <div className="border rounded-lg p-5 space-y-3 bg-white">
          <h2 className="font-semibold text-slate-800">Kunde *</h2>
          <CustomerPicker value={customer} onChange={setCustomer} />
        </div>

        {/* Rechnungsdaten */}
        <div className="border rounded-lg p-5 bg-white space-y-4">
          <h2 className="font-semibold text-slate-800">Rechnungsdaten</h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Rechnungsdatum *</Label>
              <Input
                type="date"
                value={invoiceDate}
                onChange={(e) => handleInvoiceDateChange(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label>Fällig am *</Label>
              <Input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label>Leistungszeitraum von</Label>
              <Input type="date" value={periodFrom} onChange={(e) => setPeriodFrom(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Leistungszeitraum bis</Label>
              <Input type="date" value={periodTo} onChange={(e) => setPeriodTo(e.target.value)} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Notiz (erscheint auf der Rechnung)</Label>
            <textarea
              className="w-full min-h-[80px] rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none"
              placeholder="z.B. Vielen Dank für Ihren Auftrag."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>
        </div>

        {/* Positionen */}
        <div className="border rounded-lg bg-white overflow-hidden">
          <div className="px-5 py-4 border-b flex items-center justify-between">
            <h2 className="font-semibold text-slate-800">Positionen</h2>
            <Button type="button" variant="outline" size="sm" onClick={() => setItems((prev) => [...prev, newItem()])}>
              <Plus className="h-4 w-4 mr-1" /> Position hinzufügen
            </Button>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b">
                <tr>
                  <th className="px-3 py-2 text-left font-medium text-slate-600 w-40">Artikel</th>
                  <th className="px-3 py-2 text-left font-medium text-slate-600">Beschreibung *</th>
                  <th className="px-3 py-2 text-right font-medium text-slate-600 w-20">Menge</th>
                  <th className="px-3 py-2 text-left font-medium text-slate-600 w-36">Einheit</th>
                  <th className="px-3 py-2 text-right font-medium text-slate-600 w-28">Preis (Netto)</th>
                  <th className="px-3 py-2 text-right font-medium text-slate-600 w-20">MwSt. %</th>
                  <th className="px-3 py-2 text-right font-medium text-slate-600 w-28">Gesamt (Brutto)</th>
                  <th className="px-3 py-2 w-10"></th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {items.map((item) => {
                  const { gross } = calcItem(item)
                  return (
                    <tr key={item._key} className="hover:bg-slate-50/50">
                      <td className="px-3 py-2">
                        <button
                          type="button"
                          onClick={() => setDrawerKey(item._key)}
                          className={cn(
                            'w-full h-8 px-2 rounded-md border text-xs text-left truncate transition-colors',
                            item.article_name
                              ? 'border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100'
                              : 'border-dashed border-slate-300 text-slate-400 hover:border-slate-400 hover:text-slate-500'
                          )}
                          title={item.article_name || undefined}
                        >
                          {item.article_name || 'Artikel wählen …'}
                        </button>
                      </td>
                      <td className="px-3 py-2">
                        <Input
                          className="h-8 text-sm"
                          placeholder="Beschreibung..."
                          value={item.description}
                          onChange={(e) => updateItem(item._key, 'description', e.target.value)}
                        />
                      </td>
                      <td className="px-3 py-2">
                        <Input
                          type="number"
                          className="h-8 text-sm text-right [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                          min="0"
                          step="0.001"
                          placeholder="0"
                          value={item.quantity}
                          onChange={(e) => updateItem(item._key, 'quantity', e.target.value)}
                        />
                      </td>
                      <td className="px-3 py-2">
                        <Input
                          className="h-8 text-sm"
                          placeholder="Stk."
                          value={item.unit}
                          onChange={(e) => updateItem(item._key, 'unit', e.target.value)}
                        />
                      </td>
                      <td className="px-3 py-2">
                        <Input
                          type="number"
                          className="h-8 text-sm text-right [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                          min="0"
                          step="0.01"
                          placeholder="0,00"
                          value={item.unit_price_net}
                          onChange={(e) => updateItem(item._key, 'unit_price_net', e.target.value)}
                        />
                      </td>
                      <td className="px-3 py-2">
                        <div className="h-8 px-2 flex items-center justify-end text-sm text-slate-600 bg-slate-50 border border-slate-200 rounded-md">
                          {item.vat_rate ? `${parseFloat(item.vat_rate).toFixed(0)} %` : '–'}
                        </div>
                      </td>
                      <td className="px-3 py-2 text-right font-medium text-slate-700 whitespace-nowrap">
                        {gross > 0 ? formatCurrency(gross) : '–'}
                      </td>
                      <td className="px-3 py-2">
                        <button
                          type="button"
                          className="text-slate-400 hover:text-red-500 transition-colors"
                          onClick={() => removeItem(item._key)}
                          title="Position entfernen"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  )
                })}
                {items.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-5 py-8 text-center text-slate-400 text-sm">
                      Keine Positionen — klicken Sie auf „Position hinzufügen"
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Totals */}
          <div className="border-t px-5 py-4 flex justify-end">
            <div className="w-64 space-y-1.5 text-sm">
              <div className="flex justify-between text-slate-600">
                <span>Nettobetrag</span>
                <span>{formatCurrency(totals.net)}</span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>MwSt.</span>
                <span>{formatCurrency(totals.vat)}</span>
              </div>
              <div className="flex justify-between font-semibold text-slate-900 text-base border-t pt-1.5">
                <span>Gesamtbetrag</span>
                <span>{formatCurrency(totals.gross)}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Submit */}
        <div className="flex justify-end gap-2 pb-6">
          <Button type="button" variant="outline" onClick={() => navigate('/invoices')}>
            Abbrechen
          </Button>
          <Button type="submit" disabled={createMutation.isPending}>
            {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Rechnung speichern
          </Button>
        </div>
      </form>
    </div>
  )
}
