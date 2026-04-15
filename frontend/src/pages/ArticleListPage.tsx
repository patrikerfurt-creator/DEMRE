import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Plus, Search, Upload, Pencil, Trash2, Loader2, AlertCircle, CheckCircle } from 'lucide-react'
import api from '@/lib/api'
import type { Article } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { toast } from '@/hooks/use-toast'
import { formatCurrency } from '@/lib/utils'

function normalizeDecimal(v: string) { return v.replace(',', '.') }
function isValidNumber(v: string) { return v.trim() !== '' && !isNaN(parseFloat(normalizeDecimal(v))) }

const schema = z.object({
  article_number: z.string().min(1),
  name: z.string().min(1),
  description: z.string().optional(),
  unit: z.string().optional(),
  unit_price: z.string().min(1).refine(isValidNumber, { message: 'Ungültige Zahl' }),
  vat_rate: z.string().min(1).refine(isValidNumber, { message: 'Ungültige Zahl' }).default('19.00'),
  category: z.string().optional(),
  is_active: z.boolean().default(true),
})
type FormData = z.infer<typeof schema>

export function ArticleListPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [editing, setEditing] = useState<Article | null>(null)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [previewRows, setPreviewRows] = useState<any[]>([])
  const [previewLoading, setPreviewLoading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const { data: articles, isLoading } = useQuery({
    queryKey: ['articles', search],
    queryFn: () =>
      api.get<Article[]>('/articles', {
        params: { search: search || undefined, page_size: 100 },
      }).then((r) => r.data),
  })

  const { register, handleSubmit, reset, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  })

  function formatApiError(err: any): string {
    const detail = err?.response?.data?.detail
    if (!detail) return err?.message || 'Unbekannter Fehler'
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((e: any) => e.msg || JSON.stringify(e)).join(' | ')
    return JSON.stringify(detail)
  }

  const createMutation = useMutation({
    mutationFn: (data: FormData) => api.post('/articles', {
      ...data,
      unit_price: parseFloat(normalizeDecimal(data.unit_price)),
      vat_rate: parseFloat(normalizeDecimal(data.vat_rate)),
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['articles'] })
      setDialogOpen(false)
      toast({ title: 'Artikel erstellt' })
    },
    onError: (err: any) => {
      toast({ title: 'Fehler beim Speichern', description: formatApiError(err), variant: 'destructive' })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: FormData }) =>
      api.put(`/articles/${id}`, {
        ...data,
        unit_price: parseFloat(normalizeDecimal(data.unit_price)),
        vat_rate: parseFloat(normalizeDecimal(data.vat_rate)),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['articles'] })
      setDialogOpen(false)
      toast({ title: 'Artikel aktualisiert' })
    },
    onError: (err: any) => {
      toast({ title: 'Fehler beim Speichern', description: formatApiError(err), variant: 'destructive' })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/articles/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['articles'] })
      toast({ title: 'Artikel gelöscht' })
    },
  })

  const confirmImportMutation = useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      return api.post('/articles/import/confirm', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    },
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['articles'] })
      setImportOpen(false)
      setPreviewRows([])
      setImportFile(null)
      toast({ title: `${res.data.length} Artikel importiert` })
    },
    onError: (err: any) => {
      toast({ title: 'Fehler', description: err?.response?.data?.detail, variant: 'destructive' })
    },
  })

  async function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setImportFile(file)
    setPreviewLoading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await api.post('/articles/import/preview', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setPreviewRows(res.data)
    } catch {
      toast({ title: 'Fehler beim Lesen der CSV-Datei', variant: 'destructive' })
    } finally {
      setPreviewLoading(false)
    }
  }

  function openEdit(a: Article) {
    setEditing(a)
    reset({
      article_number: a.article_number,
      name: a.name,
      description: a.description || '',
      unit: a.unit || '',
      unit_price: a.unit_price,
      vat_rate: a.vat_rate,
      category: a.category || '',
      is_active: a.is_active,
    })
    setDialogOpen(true)
  }

  function openCreate() {
    setEditing(null)
    reset({ vat_rate: '19.00', is_active: true })
    setDialogOpen(true)
  }

  function onSubmit(data: FormData) {
    if (editing) {
      updateMutation.mutate({ id: editing.id, data })
    } else {
      createMutation.mutate(data)
    }
  }

  const items = Array.isArray(articles) ? articles : []

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Artikel</h1>
          <p className="text-sm text-slate-500 mt-1">{items.length} Artikel</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setImportOpen(true)}>
            <Upload className="h-4 w-4 mr-2" /> CSV importieren
          </Button>
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4 mr-2" /> Neuer Artikel
          </Button>
        </div>
      </div>

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder="Suche nach Nummer, Name, Kategorie..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="border rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Artikelnummer</TableHead>
              <TableHead>Bezeichnung</TableHead>
              <TableHead>Kategorie</TableHead>
              <TableHead>Einheit</TableHead>
              <TableHead className="text-right">Preis netto</TableHead>
              <TableHead className="text-right">MwSt.</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-24">Aktionen</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center py-12">
                  <Loader2 className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
                </TableCell>
              </TableRow>
            ) : items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center text-muted-foreground py-12">
                  Keine Artikel gefunden
                </TableCell>
              </TableRow>
            ) : (
              items.map((a) => (
                <TableRow key={a.id}>
                  <TableCell className="font-mono text-sm">{a.article_number}</TableCell>
                  <TableCell>
                    <div className="font-medium">{a.name}</div>
                    {a.description && <div className="text-xs text-muted-foreground truncate max-w-xs">{a.description}</div>}
                  </TableCell>
                  <TableCell>{a.category || '–'}</TableCell>
                  <TableCell>{a.unit || '–'}</TableCell>
                  <TableCell className="text-right">{formatCurrency(a.unit_price)}</TableCell>
                  <TableCell className="text-right">{parseFloat(a.vat_rate).toFixed(0)}%</TableCell>
                  <TableCell>
                    <Badge variant={a.is_active ? 'default' : 'secondary'}>
                      {a.is_active ? 'Aktiv' : 'Inaktiv'}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="icon" onClick={() => openEdit(a)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => {
                          if (confirm(`Artikel "${a.article_number}" löschen?`)) {
                            deleteMutation.mutate(a.id)
                          }
                        }}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="flex flex-col max-h-[90vh] p-0 gap-0">
          <DialogHeader className="px-6 pt-6 pb-4 border-b shrink-0">
            <DialogTitle>{editing ? 'Artikel bearbeiten' : 'Neuer Artikel'}</DialogTitle>
          </DialogHeader>
          <form
            onSubmit={handleSubmit(onSubmit, (errs) => {
              const fields = Object.keys(errs).map((k) => ({
                article_number: 'Artikelnummer',
                name: 'Bezeichnung',
                unit_price: 'Einzelpreis',
              } as Record<string, string>)[k] ?? k).join(', ')
              toast({ title: 'Pflichtfelder fehlen', description: fields, variant: 'destructive' })
            })}
            className="flex flex-col flex-1 min-h-0"
          >
            <div className="overflow-y-auto flex-1 px-6 py-5 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label>Artikelnummer *</Label>
                  <Input {...register('article_number')} className={errors.article_number ? 'border-destructive' : ''} />
                  {errors.article_number && <p className="text-xs text-destructive">Pflichtfeld</p>}
                </div>
                <div className="space-y-1">
                  <Label>Bezeichnung *</Label>
                  <Input {...register('name')} className={errors.name ? 'border-destructive' : ''} />
                  {errors.name && <p className="text-xs text-destructive">Pflichtfeld</p>}
                </div>
                <div className="space-y-1">
                  <Label>Einzelpreis netto *</Label>
                  <Input inputMode="decimal" placeholder="z.B. 19.90" className={errors.unit_price ? 'border-destructive' : ''} {...register('unit_price')} />
                  {errors.unit_price && <p className="text-xs text-destructive">{errors.unit_price.message || 'Pflichtfeld'}</p>}
                </div>
                <div className="space-y-1">
                  <Label>MwSt.-Satz (%)</Label>
                  <Input inputMode="decimal" placeholder="19.00" {...register('vat_rate')} />
                </div>
                <div className="space-y-1">
                  <Label>Einheit</Label>
                  <Input {...register('unit')} placeholder="Stk., m², Monat..." />
                </div>
                <div className="space-y-1">
                  <Label>Kategorie</Label>
                  <Input {...register('category')} />
                </div>
              </div>
              <div className="space-y-1">
                <Label>Beschreibung</Label>
                <Input {...register('description')} />
              </div>
            </div>
            <DialogFooter className="px-6 py-4 border-t shrink-0">
              <Button variant="outline" type="button" onClick={() => setDialogOpen(false)}>Abbrechen</Button>
              <Button type="submit" disabled={createMutation.isPending || updateMutation.isPending}>
                {(createMutation.isPending || updateMutation.isPending) && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {editing ? 'Speichern' : 'Erstellen'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Import Dialog */}
      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Artikel aus CSV importieren</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="text-sm text-muted-foreground">
              Erwartete Spalten: article_number, name, description, unit, unit_price, vat_rate, category
            </div>
            <div className="flex items-center gap-3">
              <input
                ref={fileRef}
                type="file"
                accept=".csv"
                className="hidden"
                onChange={handleFileSelect}
              />
              <Button variant="outline" onClick={() => fileRef.current?.click()}>
                <Upload className="h-4 w-4 mr-2" /> CSV-Datei wählen
              </Button>
              {importFile && <span className="text-sm text-muted-foreground">{importFile.name}</span>}
            </div>

            {previewLoading && (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Vorschau wird geladen...
              </div>
            )}

            {previewRows.length > 0 && (
              <div className="border rounded-lg overflow-auto max-h-80">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-10">Zeile</TableHead>
                      <TableHead>Nummer</TableHead>
                      <TableHead>Bezeichnung</TableHead>
                      <TableHead>Preis</TableHead>
                      <TableHead>MwSt.</TableHead>
                      <TableHead>Gültig</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {previewRows.map((row) => (
                      <TableRow key={row.row_number} className={row.is_valid ? '' : 'bg-red-50'}>
                        <TableCell className="text-xs text-muted-foreground">{row.row_number}</TableCell>
                        <TableCell className="font-mono text-sm">{row.article_number}</TableCell>
                        <TableCell>{row.name}</TableCell>
                        <TableCell>{row.unit_price ? formatCurrency(row.unit_price) : '–'}</TableCell>
                        <TableCell>{row.vat_rate ? `${row.vat_rate}%` : '–'}</TableCell>
                        <TableCell>
                          {row.is_valid ? (
                            <CheckCircle className="h-4 w-4 text-green-500" />
                          ) : (
                            <div className="flex items-center gap-1 text-red-500">
                              <AlertCircle className="h-4 w-4" />
                              <span className="text-xs">{row.errors.join(', ')}</span>
                            </div>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setImportOpen(false); setPreviewRows([]) }}>
              Abbrechen
            </Button>
            <Button
              disabled={!importFile || previewRows.filter(r => r.is_valid).length === 0 || confirmImportMutation.isPending}
              onClick={() => importFile && confirmImportMutation.mutate(importFile)}
            >
              {confirmImportMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {previewRows.filter(r => r.is_valid).length} Artikel importieren
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
