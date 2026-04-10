import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Plus, Trash2, Loader2, AlertTriangle, Search, X, ChevronRight } from 'lucide-react'
import api from '@/lib/api'
import type { Contract, ContractItem, Article } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { toast } from '@/hooks/use-toast'
import { formatDate, formatCurrency, CONTRACT_STATUS_LABELS, BILLING_PERIOD_LABELS, cn } from '@/lib/utils'

// ── Article Drawer ─────────────────────────────────────────────────────────────

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
    queryKey: ['articles-contract-drawer', search],
    queryFn: () =>
      api.get<Article[]>('/articles', {
        params: { search: search || undefined, is_active: true, page_size: 200 },
      }).then((r) => r.data),
    enabled: open,
  })

  useEffect(() => {
    if (!open) setSearch('')
  }, [open])

  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  const articles = Array.isArray(data) ? data : []

  return createPortal(
    <div className={cn(
      'fixed top-0 right-0 z-[200] h-full w-96 bg-white shadow-2xl flex flex-col transition-transform duration-300 ease-in-out',
      open ? 'translate-x-0' : 'translate-x-full pointer-events-none'
    )}>
        <div className="flex items-center justify-between px-5 py-4 border-b bg-slate-50">
          <h3 className="font-semibold text-slate-800">Artikel auswählen</h3>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="px-4 py-3 border-b">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <Input className="pl-9" placeholder="Artikel suchen..." value={search} onChange={(e) => setSearch(e.target.value)} autoFocus />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
            </div>
          ) : articles.length === 0 ? (
            <div className="px-5 py-8 text-center text-sm text-slate-400">Keine Artikel gefunden</div>
          ) : (
            <ul className="divide-y">
              {articles.map((a) => (
                <li key={a.id}>
                  <button
                    type="button"
                    className="w-full text-left px-5 py-3.5 hover:bg-blue-50 transition-colors flex items-center gap-3 group"
                    onClick={() => { onSelect(a); onClose() }}
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
                    </div>
                    <ChevronRight className="h-4 w-4 text-slate-300 group-hover:text-blue-400 flex-shrink-0" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="px-5 py-3 border-t bg-slate-50 text-xs text-slate-400">
          {articles.length > 0 && `${articles.length} Artikel`}
        </div>
      </div>,
    document.body
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────────

export function ContractDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [itemDialogOpen, setItemDialogOpen] = useState(false)
  const [articleDrawerOpen, setArticleDrawerOpen] = useState(false)
  const articleDrawerOpenRef = useRef(false)
  const [editingItem, setEditingItem] = useState<ContractItem | null>(null)
  const [selectedArticle, setSelectedArticle] = useState<Article | null>(null)
  const [itemForm, setItemForm] = useState({
    quantity: '1',
    override_price: '',
    override_vat_rate: '',
    description_override: '',
    billing_period: 'monthly',
    sort_order: '0',
    valid_from: '',
    valid_until: '',
  })

  const { data: contract, isLoading } = useQuery({
    queryKey: ['contract', id],
    queryFn: () => api.get<Contract>(`/contracts/${id}`).then((r) => r.data),
    enabled: !!id,
  })

  const terminateMutation = useMutation({
    mutationFn: () => api.post(`/contracts/${id}/terminate`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract', id] })
      toast({ title: 'Vertrag gekündigt' })
    },
  })

  const addItemMutation = useMutation({
    mutationFn: (data: any) => api.post(`/contracts/${id}/items`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract', id] })
      setItemDialogOpen(false)
      resetItemForm()
      toast({ title: 'Position hinzugefügt' })
    },
    onError: (err: any) => {
      toast({ title: 'Fehler', description: err?.response?.data?.detail, variant: 'destructive' })
    },
  })

  const updateItemMutation = useMutation({
    mutationFn: ({ itemId, data }: { itemId: string; data: any }) =>
      api.put(`/contracts/${id}/items/${itemId}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract', id] })
      setItemDialogOpen(false)
      setEditingItem(null)
      toast({ title: 'Position aktualisiert' })
    },
  })

  const deleteItemMutation = useMutation({
    mutationFn: (itemId: string) => api.delete(`/contracts/${id}/items/${itemId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract', id] })
      toast({ title: 'Position gelöscht' })
    },
  })

  function resetItemForm() {
    setItemForm({ quantity: '1', override_price: '', override_vat_rate: '', description_override: '', billing_period: 'monthly', sort_order: '0', valid_from: '', valid_until: '' })
    setSelectedArticle(null)
  }

  function openArticleDrawer() {
    articleDrawerOpenRef.current = true
    setArticleDrawerOpen(true)
  }

  function closeArticleDrawer() {
    setArticleDrawerOpen(false)
    articleDrawerOpenRef.current = false
  }

  function openAddItem() {
    setEditingItem(null)
    resetItemForm()
    setItemDialogOpen(true)
  }

  function openEditItem(item: ContractItem) {
    setEditingItem(item)
    setSelectedArticle(null)
    setItemForm({
      quantity: item.quantity,
      override_price: item.override_price || '',
      override_vat_rate: item.override_vat_rate || '',
      description_override: item.description_override || '',
      billing_period: item.billing_period,
      sort_order: String(item.sort_order),
      valid_from: item.valid_from || '',
      valid_until: item.valid_until || '',
    })
    setItemDialogOpen(true)
  }

  function handleArticleSelect(a: Article) {
    setSelectedArticle(a)
    setItemForm(p => ({
      ...p,
      description_override: p.description_override || a.name,
      override_price: p.override_price || a.unit_price,
      override_vat_rate: p.override_vat_rate || a.vat_rate,
    }))
  }

  function handleItemSubmit(e: React.FormEvent) {
    e.preventDefault()
    const data = {
      article_id: selectedArticle?.id || (editingItem?.article_id) || undefined,
      quantity: parseFloat(itemForm.quantity),
      override_price: itemForm.override_price ? parseFloat(itemForm.override_price) : null,
      override_vat_rate: itemForm.override_vat_rate ? parseFloat(itemForm.override_vat_rate) : null,
      description_override: itemForm.description_override || null,
      billing_period: itemForm.billing_period,
      sort_order: parseInt(itemForm.sort_order),
      valid_from: itemForm.valid_from || null,
      valid_until: itemForm.valid_until || null,
      is_active: true,
    }
    if (editingItem) {
      updateItemMutation.mutate({ itemId: editingItem.id, data })
    } else {
      addItemMutation.mutate(data)
    }
  }

  if (isLoading) return <div className="p-6 text-muted-foreground">Lädt...</div>
  if (!contract) return <div className="p-6 text-muted-foreground">Vertrag nicht gefunden</div>

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/contracts')}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Vertrag {contract.contract_number}</h1>
          <p className="text-sm text-slate-500">{contract.property_ref || 'Kein Objekt angegeben'}</p>
        </div>
        <Badge variant={contract.status === 'active' ? 'default' : 'destructive'} className="ml-auto">
          {CONTRACT_STATUS_LABELS[contract.status]}
        </Badge>
        {contract.status === 'active' && (
          <Button variant="outline" size="sm" className="text-destructive border-destructive"
            onClick={() => { if (confirm('Vertrag wirklich kündigen?')) terminateMutation.mutate() }}>
            <AlertTriangle className="h-4 w-4 mr-2" /> Kündigen
          </Button>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card><CardContent className="pt-4"><div className="text-xs text-muted-foreground">Start</div><div className="font-medium">{formatDate(contract.start_date)}</div></CardContent></Card>
        <Card><CardContent className="pt-4"><div className="text-xs text-muted-foreground">Ende</div><div className="font-medium">{formatDate(contract.end_date)}</div></CardContent></Card>
        <Card><CardContent className="pt-4"><div className="text-xs text-muted-foreground">Abrechnungstag</div><div className="font-medium">{contract.billing_day}. des Monats</div></CardContent></Card>
        <Card><CardContent className="pt-4"><div className="text-xs text-muted-foreground">Zahlungsziel</div><div className="font-medium">{contract.payment_terms_days} Tage</div></CardContent></Card>
      </div>

      {/* Items */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">Vertragspositionen</h2>
          {contract.status === 'active' && (
            <Button size="sm" onClick={openAddItem}>
              <Plus className="h-4 w-4 mr-2" /> Position hinzufügen
            </Button>
          )}
        </div>
        <div className="border rounded-lg">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Reihenfolge</TableHead>
                <TableHead>Beschreibung / Artikel</TableHead>
                <TableHead>Abrechnungsintervall</TableHead>
                <TableHead>Gültigkeit</TableHead>
                <TableHead className="text-right">Menge</TableHead>
                <TableHead className="text-right">Preis (Override)</TableHead>
                <TableHead className="text-right">MwSt.</TableHead>
                <TableHead>Aktiv</TableHead>
                <TableHead className="w-24">Aktionen</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {contract.items.length === 0 ? (
                <TableRow><TableCell colSpan={8} className="text-center text-muted-foreground py-8">Keine Positionen vorhanden</TableCell></TableRow>
              ) : contract.items.sort((a, b) => a.sort_order - b.sort_order).map((item) => (
                <TableRow key={item.id} className={!item.is_active ? 'opacity-50' : undefined}>
                  <TableCell className="text-sm">{item.sort_order}</TableCell>
                  <TableCell>
                    {item.description_override || item.article_id ? (
                      item.description_override || <span className="text-muted-foreground italic">Artikel #{item.article_id?.substring(0, 8)}</span>
                    ) : '–'}
                  </TableCell>
                  <TableCell>{BILLING_PERIOD_LABELS[item.billing_period]}</TableCell>
                  <TableCell className="text-sm text-slate-600 whitespace-nowrap">
                    {item.valid_from || item.valid_until ? (
                      <>
                        {item.valid_from ? formatDate(item.valid_from) : '–'}
                        {' '}bis{' '}
                        {item.valid_until ? formatDate(item.valid_until) : '∞'}
                      </>
                    ) : (
                      <span className="text-muted-foreground text-xs">unbegrenzt</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">{String(parseFloat(item.quantity))}</TableCell>
                  <TableCell className="text-right">
                    {item.override_price ? formatCurrency(item.override_price) : <span className="text-muted-foreground text-xs">Artikelpreis</span>}
                  </TableCell>
                  <TableCell className="text-right">
                    {item.override_vat_rate ? `${item.override_vat_rate}%` : <span className="text-muted-foreground text-xs">Artikel</span>}
                  </TableCell>
                  <TableCell>
                    <Badge variant={item.is_active ? 'default' : 'secondary'} className="text-xs">
                      {item.is_active ? 'Ja' : 'Nein'}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => openEditItem(item)}>
                        <Plus className="h-3 w-3 rotate-45" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-8 w-8"
                        onClick={() => { if (confirm('Position löschen?')) deleteItemMutation.mutate(item.id) }}>
                        <Trash2 className="h-3 w-3 text-destructive" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>

      {/* Item Dialog */}
      <Dialog open={itemDialogOpen} onOpenChange={(open) => { setItemDialogOpen(open); if (!open) resetItemForm() }} modal={!articleDrawerOpen}>
        <DialogContent className="max-w-lg" onInteractOutside={(e) => { if (articleDrawerOpenRef.current) e.preventDefault() }}>
          <DialogHeader>
            <DialogTitle>{editingItem ? 'Position bearbeiten' : 'Position hinzufügen'}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleItemSubmit} className="space-y-4">

            {/* Artikel */}
            <div className="space-y-2">
              <Label>Artikel</Label>
              {selectedArticle ? (
                <div className="flex items-center justify-between px-3 py-2 rounded-md border border-blue-200 bg-blue-50">
                  <div>
                    <span className="font-medium text-sm text-blue-800">{selectedArticle.name}</span>
                    <span className="text-xs text-blue-600 ml-2">{selectedArticle.article_number}</span>
                  </div>
                  <Button type="button" variant="outline" size="sm" onClick={openArticleDrawer}>
                    Ändern
                  </Button>
                </div>
              ) : editingItem?.article_id ? (
                <div className="flex items-center justify-between px-3 py-2 rounded-md border border-slate-200 bg-slate-50">
                  <span className="text-sm text-slate-600 italic">Artikel #{editingItem.article_id.substring(0, 8)}</span>
                  <Button type="button" variant="outline" size="sm" onClick={openArticleDrawer}>
                    Ändern
                  </Button>
                </div>
              ) : (
                <Button type="button" variant="outline" className="w-full justify-start text-muted-foreground" onClick={openArticleDrawer}>
                  <Search className="h-4 w-4 mr-2" /> Artikel auswählen…
                </Button>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Beschreibung (Override)</Label>
                <Input value={itemForm.description_override} onChange={(e) => setItemForm(p => ({ ...p, description_override: e.target.value }))} placeholder="Leer = Artikelname" />
              </div>
              <div className="space-y-2">
                <Label>Abrechnungsintervall</Label>
                <Select value={itemForm.billing_period} onValueChange={(v) => setItemForm(p => ({ ...p, billing_period: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(BILLING_PERIOD_LABELS).map(([k, v]) => (
                      <SelectItem key={k} value={k}>{v}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Menge</Label>
                <Input type="number" step="0.001" className="[appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none" value={itemForm.quantity} onChange={(e) => setItemForm(p => ({ ...p, quantity: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Preis Override (netto)</Label>
                <Input type="number" step="0.0001" className="[appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none" value={itemForm.override_price} onChange={(e) => setItemForm(p => ({ ...p, override_price: e.target.value }))} placeholder="Leer = Artikelpreis" />
              </div>
              <div className="space-y-2">
                <Label>MwSt. Override (%)</Label>
                <Input type="number" step="0.01" className="[appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none" value={itemForm.override_vat_rate} onChange={(e) => setItemForm(p => ({ ...p, override_vat_rate: e.target.value }))} placeholder="Leer = Artikel-MwSt." />
              </div>
              <div className="space-y-2">
                <Label>Reihenfolge</Label>
                <Input type="number" className="[appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none" value={itemForm.sort_order} onChange={(e) => setItemForm(p => ({ ...p, sort_order: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Gültig ab</Label>
                <Input type="date" value={itemForm.valid_from} onChange={(e) => setItemForm(p => ({ ...p, valid_from: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Gültig bis</Label>
                <Input type="date" value={itemForm.valid_until} onChange={(e) => setItemForm(p => ({ ...p, valid_until: e.target.value }))} />
              </div>
            </div>

            <DialogFooter>
              <Button variant="outline" type="button" onClick={() => { setItemDialogOpen(false); resetItemForm() }}>Abbrechen</Button>
              <Button type="submit" disabled={addItemMutation.isPending || updateItemMutation.isPending}>
                {(addItemMutation.isPending || updateItemMutation.isPending) && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {editingItem ? 'Speichern' : 'Hinzufügen'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Article Drawer */}
      <ArticleDrawer
        open={articleDrawerOpen}
        onClose={closeArticleDrawer}
        onSelect={handleArticleSelect}
      />
    </div>
  )
}
