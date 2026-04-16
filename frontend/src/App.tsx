import { Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { AppShell } from '@/components/layout/AppShell'
import { LoginPage } from '@/pages/LoginPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { CustomerListPage } from '@/pages/CustomerListPage'
import { CustomerDetailPage } from '@/pages/CustomerDetailPage'
import { ArticleListPage } from '@/pages/ArticleListPage'
import { ContractListPage } from '@/pages/ContractListPage'
import { ContractDetailPage } from '@/pages/ContractDetailPage'
import { InvoiceListPage } from '@/pages/InvoiceListPage'
import { InvoiceDetailPage } from '@/pages/InvoiceDetailPage'
import { InvoiceCreatePage } from '@/pages/InvoiceCreatePage'
import { ExportsPage } from '@/pages/ExportsPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { CreditorListPage } from '@/pages/CreditorListPage'
import { CreditorDetailPage } from '@/pages/CreditorDetailPage'
import { IncomingInvoiceListPage } from '@/pages/IncomingInvoiceListPage'
import { ExpenseReceiptListPage } from '@/pages/ExpenseReceiptListPage'
import { MitarbeiterListPage } from '@/pages/MitarbeiterListPage'

function RequireAuth() {
  const token = useAuthStore((s) => s.token)
  if (!token) {
    return <Navigate to="/login" replace />
  }
  return <Outlet />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/customers" element={<CustomerListPage />} />
          <Route path="/customers/:id" element={<CustomerDetailPage />} />
          <Route path="/articles" element={<ArticleListPage />} />
          <Route path="/contracts" element={<ContractListPage />} />
          <Route path="/contracts/:id" element={<ContractDetailPage />} />
          <Route path="/invoices" element={<InvoiceListPage />} />
          <Route path="/invoices/new" element={<InvoiceCreatePage />} />
          <Route path="/invoices/:id" element={<InvoiceDetailPage />} />
          <Route path="/exports" element={<ExportsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/creditors" element={<CreditorListPage />} />
          <Route path="/creditors/:id" element={<CreditorDetailPage />} />
          <Route path="/incoming-invoices" element={<IncomingInvoiceListPage />} />
          <Route path="/expense-receipts" element={<ExpenseReceiptListPage />} />
          <Route path="/mitarbeiter" element={<MitarbeiterListPage />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
