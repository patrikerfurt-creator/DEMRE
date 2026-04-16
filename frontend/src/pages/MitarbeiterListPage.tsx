import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Plus, Pencil, Trash2, Loader2, UserCheck, UserX } from 'lucide-react'
import api from '@/lib/api'
import type { User } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog'
import { toast } from '@/hooks/use-toast'
import { validateIban, lookupBicFromIban } from '@/lib/utils'

const roleLabels: Record<string, string> = {
  admin: 'Admin',
  user: 'Mitarbeiter',
  readonly: 'Nur-Lesen',
}

const schema = z.object({
  full_name: z.string().min(1, 'Name ist erforderlich'),
  email: z.string().email('Ungültige E-Mail'),
  role: z.enum(['admin', 'user', 'readonly']),
  is_active: z.boolean(),
  iban: z.string().optional().refine(
    (val) => !val || validateIban(val),
    { message: 'Ungültige IBAN' }
  ),
  bic: z.string().optional(),
  password: z.string().optional(),
})
type FormData = z.infer<typeof schema>

function formatApiError(err: any): string {
  const detail = err?.response?.data?.detail
  if (!detail) return 'Unbekannter Fehler'
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d: any) => d.msg || JSON.stringify(d)).join(', ')
  return JSON.stringify(detail)
}

export function MitarbeiterListPage() {
  const queryClient = useQueryClient()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [editing, setEditing] = useState<User | null>(null)
  const [toDelete, setToDelete] = useState<User | null>(null)
  const [bicLoading, setBicLoading] = useState(false)

  const { data: users = [], isLoading } = useQuery<User[]>({
    queryKey: ['users'],
    queryFn: () => api.get<User[]>('/users').then((r) => r.data),
  })

  const { register, handleSubmit, reset, setValue, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { role: 'user', is_active: true },
  })

  function openCreate() {
    setEditing(null)
    reset({ full_name: '', email: '', role: 'user', is_active: true, iban: '', bic: '', password: '' })
    setDialogOpen(true)
  }

  function openEdit(user: User) {
    setEditing(user)
    reset({
      full_name: user.full_name,
      email: user.email,
      role: user.role,
      is_active: user.is_active,
      iban: user.iban ?? '',
      bic: user.bic ?? '',
      password: '',
    })
    setDialogOpen(true)
  }

  const createMutation = useMutation({
    mutationFn: (data: FormData) => api.post('/users', { ...data, password: data.password || 'Temp1234!' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setDialogOpen(false)
      toast({ title: 'Mitarbeiter angelegt' })
    },
    onError: (err: any) => toast({ title: 'Fehler', description: formatApiError(err), variant: 'destructive' }),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: FormData }) => {
      const payload: Record<string, any> = {
        full_name: data.full_name,
        email: data.email,
        role: data.role,
        is_active: data.is_active,
        iban: data.iban || null,
        bic: data.bic || null,
      }
      if (data.password) payload.password = data.password
      return api.put(`/users/${id}`, payload)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setDialogOpen(false)
      toast({ title: 'Mitarbeiter aktualisiert' })
    },
    onError: (err: any) => toast({ title: 'Fehler', description: formatApiError(err), variant: 'destructive' }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/users/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setDeleteDialogOpen(false)
      setToDelete(null)
      toast({ title: 'Mitarbeiter gelöscht' })
    },
    onError: (err: any) => toast({ title: 'Fehler', description: formatApiError(err), variant: 'destructive' }),
  })

  function onSubmit(data: FormData) {
    if (editing) {
      updateMutation.mutate({ id: editing.id, data })
    } else {
      createMutation.mutate(data)
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Mitarbeiter</h1>
          <p className="text-sm text-slate-500 mt-1">Benutzerkonten und Bankverbindungen verwalten</p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4 mr-2" />
          Mitarbeiter anlegen
        </Button>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 text-slate-500 p-4">
          <Loader2 className="h-4 w-4 animate-spin" />
          Lädt...
        </div>
      ) : (
        <div className="border rounded-lg overflow-hidden bg-white">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>E-Mail</TableHead>
                <TableHead>Rolle</TableHead>
                <TableHead>IBAN</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Aktionen</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-slate-400 py-8">
                    Keine Mitarbeiter vorhanden
                  </TableCell>
                </TableRow>
              ) : (
                users.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell className="font-medium">{user.full_name}</TableCell>
                    <TableCell className="text-slate-600">{user.email}</TableCell>
                    <TableCell>
                      <Badge variant={user.role === 'admin' ? 'default' : 'secondary'}>
                        {roleLabels[user.role] ?? user.role}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-slate-600 font-mono text-sm">
                      {user.iban || <span className="text-slate-300">—</span>}
                    </TableCell>
                    <TableCell>
                      {user.is_active ? (
                        <span className="inline-flex items-center gap-1 text-green-700 text-sm">
                          <UserCheck className="h-3.5 w-3.5" />
                          Aktiv
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-slate-400 text-sm">
                          <UserX className="h-3.5 w-3.5" />
                          Inaktiv
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button size="sm" variant="ghost" onClick={() => openEdit(user)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-red-500 hover:text-red-700"
                          onClick={() => { setToDelete(user); setDeleteDialogOpen(true) }}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Anlegen / Bearbeiten Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg flex flex-col max-h-[90vh]">
          <DialogHeader className="shrink-0">
            <DialogTitle>{editing ? 'Mitarbeiter bearbeiten' : 'Mitarbeiter anlegen'}</DialogTitle>
          </DialogHeader>

          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col flex-1 min-h-0">
            <div className="flex-1 overflow-y-auto space-y-4 pr-1">
              <div className="space-y-2">
                <Label>Name *</Label>
                <Input {...register('full_name')} placeholder="Max Mustermann" />
                {errors.full_name && <p className="text-xs text-red-500">{errors.full_name.message}</p>}
              </div>

              <div className="space-y-2">
                <Label>E-Mail *</Label>
                <Input {...register('email')} type="email" placeholder="max@demme-immobilien.de" />
                {errors.email && <p className="text-xs text-red-500">{errors.email.message}</p>}
              </div>

              <div className="space-y-2">
                <Label>Rolle</Label>
                <select
                  {...register('role')}
                  className="w-full border border-input rounded-md px-3 py-2 text-sm bg-background"
                >
                  <option value="user">Mitarbeiter</option>
                  <option value="admin">Admin</option>
                  <option value="readonly">Nur-Lesen</option>
                </select>
              </div>

              <div className="space-y-2">
                <Label>{editing ? 'Neues Passwort (leer lassen = unverändert)' : 'Passwort'}</Label>
                <Input
                  {...register('password')}
                  type="password"
                  placeholder={editing ? 'Leer lassen für keine Änderung' : 'Mindestens 8 Zeichen'}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>IBAN</Label>
                  <Input
                    {...register('iban')}
                    placeholder="DE89370400440532013000"
                    className="font-mono"
                    onBlur={async (e) => {
                      const val = e.target.value.replace(/\s/g, '').toUpperCase()
                      if (!val || !validateIban(val)) return
                      setBicLoading(true)
                      const bic = await lookupBicFromIban(val)
                      setBicLoading(false)
                      if (bic) setValue('bic', bic)
                    }}
                  />
                  {errors.iban && <p className="text-xs text-red-500">{errors.iban.message}</p>}
                </div>
                <div className="space-y-2">
                  <Label>BIC</Label>
                  <div className="relative">
                    <Input {...register('bic')} placeholder="COBADEFFXXX" className="font-mono" />
                    {bicLoading && <Loader2 className="absolute right-2 top-2.5 h-4 w-4 animate-spin text-muted-foreground" />}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  id="is_active"
                  {...register('is_active')}
                  className="h-4 w-4"
                />
                <Label htmlFor="is_active">Konto aktiv</Label>
              </div>
            </div>

            <DialogFooter className="shrink-0 pt-4 border-t mt-4">
              <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                Abbrechen
              </Button>
              <Button type="submit" disabled={isPending}>
                {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {editing ? 'Speichern' : 'Anlegen'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Löschen-Bestätigung */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Mitarbeiter löschen?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-slate-600">
            <span className="font-medium">{toDelete?.full_name}</span> wird unwiderruflich gelöscht.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Abbrechen
            </Button>
            <Button
              variant="destructive"
              disabled={deleteMutation.isPending}
              onClick={() => toDelete && deleteMutation.mutate(toDelete.id)}
            >
              {deleteMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Löschen
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
