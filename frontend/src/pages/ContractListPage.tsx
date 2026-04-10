import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Loader2, Search, X, ChevronRight } from 'lucide-react'
import api from '@/lib/api'
import type { Contract, Customer } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { toast } from '@/hooks/use-toast'
import { formatDate, CONTRACT_STATUS_LABELS, cn } from '@/lib/utils'

// ── Customer Drawer ────────────────────────────────────────────────────────────

function CustomerDrawer({
  open,
  onClose,
  onSelect,
}: {
  open: boolean
  onClose: () => void
  onSelect: (c: Customer) => void
}) {
  const [search, setSearch] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['customers-drawer', search],
    queryFn: () =>
      api.get('/customers', {
        params: { search: search || undefined, is_active: true, page_size: 50 },
      }).then((r) => r.data),
    enabled: open,
  })

  useEffect(() => {
    if (!open) setSearch('')
  }, [open])

  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  const customers: Customer[] = data?.items ?? []

  return createPortal(
    <div
      className={cn(
        'fixed top-0 right-0 z-[200] h-full w-96 bg-white shadow-2xl flex flex-col transition-transform duration-300 ease-in-out',
        open ? 'translate-x-0' : 'translate-x-full pointer-events-none'
      )}
    >
      <div className="flex items-center justify-between px-5 py-4 border-b bg-slate-50">
        <h3 className="font-semibold text-slate-800">Kunde auswählen</h3>
        <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-600">
          <X className="h-5 w-5" />
        </button>
      </div>
      <div className="px-4 py-3 border-b">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <Input
            className="pl-9"
            placeholder="Name oder Kundennummer..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            autoFocus={open}
          />
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
          </div>
        ) : customers.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm text-slate-400">Keine Kunden gefunden</div>
        ) : (
          <ul className="divide-y">
            {customers.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  className="w-full text-left px-5 py-3.5 hover:bg-blue-50 transition-colors flex items-center gap-3 group"
                  onClick={() => { onSelect(c); onClose() }}
                >
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm text-slate-800 truncate">
                      {c.company_name || `${c.first_name || ''} ${c.last_name || ''}`.trim()}
                    </div>
                    <div className="text-xs text-slate-400 mt-0.5">{c.customer_number}</div>
                  </div>
                  <ChevronRight className="h-4 w-4 text-slate-300 group-hover:text-blue-400 flex-shrink-0" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="px-5 py-3 border-t bg-slate-50 text-xs text-slate-400">
        {customers.length > 0 && `${customers.length} Kunden`}
      </div>
    </div>,
    document.body
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────────

const EMPTY_FORM = {
  property_ref: '',
  start_date: '',
  end_date: '',
  billing_day: '1',
  payment_terms_days: '14',
  notes: '',
}

export function ContractListPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [customerDrawerOpen, setCustomerDrawerOpen] = useState(false)
  const drawerOpenRef = useRef(false)
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null)
  const [formData, setFormData] = useState(EMPTY_FORM)

  const { data: contracts, isLoading } = useQuery({
    queryKey: ['contracts', statusFilter],
    queryFn: () =>
      api.get<Contract[]>('/contracts', {
        params: { status: statusFilter !== 'all' ? statusFilter : undefined, page_size: 100 },
      }).then((r) => r.data),
  })

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post('/contracts', data),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['contracts'] })
      setDialogOpen(false)
      toast({ title: 'Abo-Rechnung erstellt' })
      navigate(`/contracts/${res.data.id}`)
    },
    onError: (err: any) => {
      toast({ title: 'Fehler', description: err?.response?.data?.detail, variant: 'destructive' })
    },
  })

  function openCustomerDrawer() {
    drawerOpenRef.current = true
    setCustomerDrawerOpen(true)
  }

  function closeCustomerDrawer() {
    setCustomerDrawerOpen(false)
    drawerOpenRef.current = false
  }

  function openDialog() {
    setFormData(EMPTY_FORM)
    setSelectedCustomer(null)
    setDialogOpen(true)
  }

  function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!selectedCustomer) {
      toast({ title: 'Fehler', description: 'Bitte einen Kunden wählen', variant: 'destructive' })
      return
    }
    createMutation.mutate({
      ...formData,
      customer_id: selectedCustomer.id,
      billing_day: parseInt(formData.billing_day),
      payment_terms_days: parseInt(formData.payment_terms_days),
      start_date: formData.start_date || undefined,
      end_date: formData.end_date || undefined,
    })
  }

  const items = Array.isArray(contracts) ? contracts : []
  const propertyRefs = [...new Set(items.map((c) => c.property_ref).filter(Boolean))] as string[]

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Abo-Rechnungen</h1>
          <p className="text-sm text-slate-500 mt-1">{items.length} Abo-Rechnungen</p>
        </div>
        <Button onClick={openDialog}>
          <Plus className="h-4 w-4 mr-2" /> Neue Abo-Rechnung
        </Button>
      </div>

      <div className="flex gap-2">
        {['all', 'active', 'terminated', 'suspended'].map((s) => (
          <Button key={s} variant={statusFilter === s ? 'default' : 'outline'} size="sm" onClick={() => setStatusFilter(s)}>
            {s === 'all' ? 'Alle' : CONTRACT_STATUS_LABELS[s]}
          </Button>
        ))}
      </div>

      <div className="border rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Abo-Nr.</TableHead>
              <TableHead>Kunden-ID</TableHead>
              <TableHead>Objekt</TableHead>
              <TableHead>Start</TableHead>
              <TableHead>Ende</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Positionen</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow><TableCell colSpan={7} className="text-center py-12">
                <Loader2 className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
              </TableCell></TableRow>
            ) : items.length === 0 ? (
              <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground py-12">
                Keine Abo-Rechnungen gefunden
              </TableCell></TableRow>
            ) : items.map((c) => (
              <TableRow key={c.id} className="cursor-pointer" onClick={() => navigate(`/contracts/${c.id}`)}>
                <TableCell className="font-mono text-sm">{c.contract_number}</TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">{c.customer_id.substring(0, 8)}...</TableCell>
                <TableCell>{c.property_ref || '–'}</TableCell>
                <TableCell>{formatDate(c.start_date)}</TableCell>
                <TableCell>{formatDate(c.end_date)}</TableCell>
                <TableCell>
                  <Badge variant={c.status === 'active' ? 'default' : c.status === 'terminated' ? 'destructive' : 'secondary'}>
                    {CONTRACT_STATUS_LABELS[c.status]}
                  </Badge>
                </TableCell>
                <TableCell>{c.items.length}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Create Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen} modal={!customerDrawerOpen}>
        <DialogContent className="max-w-lg" onInteractOutside={(e) => { if (drawerOpenRef.current) e.preventDefault() }}>
          <DialogHeader>
            <DialogTitle>Neue Abo-Rechnung</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">

            {/* Kunde */}
            <div className="space-y-2">
              <Label>Kunde *</Label>
              {selectedCustomer ? (
                <div className="flex items-center justify-between px-3 py-2 rounded-md border border-blue-200 bg-blue-50">
                  <div>
                    <span className="font-medium text-sm text-blue-800">{selectedCustomer.customer_number}</span>
                    <span className="text-sm text-blue-700 ml-2">
                      {selectedCustomer.company_name || `${selectedCustomer.first_name || ''} ${selectedCustomer.last_name || ''}`.trim()}
                    </span>
                  </div>
                  <Button type="button" variant="outline" size="sm" onClick={openCustomerDrawer}>
                    Ändern
                  </Button>
                </div>
              ) : (
                <Button type="button" variant="outline" className="w-full justify-start text-muted-foreground" onClick={openCustomerDrawer}>
                  <Search className="h-4 w-4 mr-2" /> Kunde auswählen…
                </Button>
              )}
            </div>

            {/* Objekt */}
            <div className="space-y-2">
              <Label>Objekt / Referenz</Label>
              <Input
                list="property-refs"
                value={formData.property_ref}
                onChange={(e) => setFormData(p => ({ ...p, property_ref: e.target.value }))}
                placeholder="Objekt wählen oder eingeben..."
              />
              <datalist id="property-refs">
                {propertyRefs.map((ref) => <option key={ref} value={ref} />)}
              </datalist>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Startdatum</Label>
                <Input type="date" value={formData.start_date} onChange={(e) => setFormData(p => ({ ...p, start_date: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Enddatum</Label>
                <Input type="date" value={formData.end_date} onChange={(e) => setFormData(p => ({ ...p, end_date: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Abrechnungstag</Label>
                <Input type="number" min="1" max="28" value={formData.billing_day} onChange={(e) => setFormData(p => ({ ...p, billing_day: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Zahlungsziel (Tage)</Label>
                <Input type="number" min="0" value={formData.payment_terms_days} onChange={(e) => setFormData(p => ({ ...p, payment_terms_days: e.target.value }))} />
              </div>
            </div>

            <DialogFooter>
              <Button variant="outline" type="button" onClick={() => setDialogOpen(false)}>Abbrechen</Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Erstellen
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Customer Drawer */}
      <CustomerDrawer
        open={customerDrawerOpen}
        onClose={closeCustomerDrawer}
        onSelect={(c) => { setSelectedCustomer(c); closeCustomerDrawer() }}
      />
    </div>
  )
}
