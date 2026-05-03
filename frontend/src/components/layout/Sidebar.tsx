import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Users, Package, FileText, Receipt,
  Download, Settings, LogOut, TrendingDown, FileInput, Wallet, FilePlus, UserCog
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/store/authStore'
import { toast } from '@/hooks/use-toast'

const debitorenItems = [
  { to: '/customers', label: 'Kunden', icon: Users },
  { to: '/articles', label: 'Artikel', icon: Package },
  { to: '/contracts', label: 'Abo-Rechnungen', icon: FileText },
  { to: '/invoices', label: 'Rechnungen', icon: Receipt, end: true },
  { to: '/invoices/new', label: 'Rechnung erstellen', icon: FilePlus },
]

const kreditorenItems = [
  { to: '/creditors', label: 'Kreditoren', icon: TrendingDown },
  { to: '/incoming-invoices', label: 'Eingangsrechnungen', icon: FileInput },
  { to: '/expense-receipts', label: 'Belege', icon: Wallet },
]

const systemItems = [
  { to: '/exports', label: 'Exporte', icon: Download },
  { to: '/settings', label: 'Einstellungen', icon: Settings },
]

const adminItems = [
  { to: '/mitarbeiter', label: 'Mitarbeiter', icon: UserCog },
]

export function Sidebar() {
  const { clearAuth, user } = useAuthStore()
  const navigate = useNavigate()

  function handleLogout() {
    clearAuth()
    toast({ title: 'Abgemeldet', description: 'Sie wurden erfolgreich abgemeldet.' })
    navigate('/login')
  }

  function NavGroup({ label, items }: { label: string; items: typeof debitorenItems }) {
    return (
      <div>
        <div className="px-3 mb-1 text-xs font-semibold text-slate-500 uppercase tracking-wider">
          {label}
        </div>
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-300 hover:bg-slate-800 hover:text-white'
              )
            }
          >
            <item.icon className="h-4 w-4 flex-shrink-0" />
            {item.label}
          </NavLink>
        ))}
      </div>
    )
  }

  return (
    <aside className="flex flex-col w-64 min-h-screen bg-slate-900 text-white">
      {/* Logo */}
      <div className="flex items-center justify-center px-6 py-4 border-b border-slate-700">
        <img src="/logo.jpg" alt="Demme Immobilienverwaltung" className="h-14 w-auto object-contain" />
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-4">
        <NavLink
          to="/dashboard"
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
              isActive
                ? 'bg-blue-600 text-white'
                : 'text-slate-300 hover:bg-slate-800 hover:text-white'
            )
          }
        >
          <LayoutDashboard className="h-4 w-4 flex-shrink-0" />
          Dashboard
        </NavLink>
        <NavGroup label="Debitoren" items={debitorenItems} />
        <NavGroup label="Kreditoren" items={kreditorenItems} />
        <NavGroup label="System" items={systemItems} />
        <div>
          {user?.role === 'admin' && (
            <>
              <div className="px-3 mb-1 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Administration
              </div>
              <NavLink
                to="/mitarbeiter"
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-blue-600 text-white'
                      : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  )
                }
              >
                <UserCog className="h-4 w-4 flex-shrink-0" />
                Mitarbeiter
              </NavLink>
            </>
          )}
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
          >
            <LogOut className="h-4 w-4 flex-shrink-0" />
            Abmelden
          </button>
        </div>
      </nav>

      {/* User */}
      <div className="px-3 py-4 border-t border-slate-700">
        <div className="flex items-center gap-3 px-3 py-2">
          <div className="h-8 w-8 rounded-full bg-blue-600 flex items-center justify-center text-xs font-bold flex-shrink-0">
            {user?.full_name?.charAt(0)?.toUpperCase() || 'U'}
          </div>
          <div className="min-w-0">
            <div className="text-sm font-medium truncate">{user?.full_name}</div>
            <div className="text-xs text-slate-400 truncate">{user?.email}</div>
          </div>
        </div>
      </div>
    </aside>
  )
}
