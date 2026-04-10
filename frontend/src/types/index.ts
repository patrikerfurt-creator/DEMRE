export type UserRole = 'admin' | 'user' | 'readonly'
export type ContractStatus = 'active' | 'terminated' | 'suspended'
export type BillingPeriod = 'monthly' | 'quarterly' | 'annual' | 'one-time'
export type InvoiceStatus = 'draft' | 'issued' | 'sent' | 'paid' | 'overdue' | 'cancelled'
export type RunType = 'invoice_generation' | 'sepa_export' | 'datev_export' | 'creditor_payment'
export type RunStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface User {
  id: string
  email: string
  full_name: string
  role: UserRole
  is_active: boolean
  created_at: string
  updated_at: string
}

export type CustomerType = 'weg' | 'company' | 'person'

export interface Customer {
  id: string
  customer_number: string
  customer_type: CustomerType
  company_name?: string
  salutation?: string
  first_name?: string
  last_name?: string
  address_line1?: string
  address_line2?: string
  postal_code?: string
  city?: string
  country_code: string
  email?: string
  phone?: string
  vat_id?: string
  tax_number?: string
  iban?: string
  bic?: string
  bank_name?: string
  account_holder?: string
  sepa_mandate_ref?: string
  sepa_mandate_date?: string
  datev_account_number?: string
  notes?: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CustomerListResponse {
  items: Customer[]
  total: number
  page: number
  page_size: number
}

export interface CustomerImportRow {
  row_number: number
  customer_number: string
  company_name?: string
  salutation?: string
  first_name?: string
  last_name?: string
  address_line1?: string
  address_line2?: string
  postal_code?: string
  city?: string
  country_code?: string
  email?: string
  phone?: string
  vat_id?: string
  tax_number?: string
  iban?: string
  bic?: string
  bank_name?: string
  account_holder?: string
  sepa_mandate_ref?: string
  sepa_mandate_date?: string
  datev_account_number?: string
  notes?: string
  errors: string[]
  is_valid: boolean
}

export interface Article {
  id: string
  article_number: string
  name: string
  description?: string
  unit?: string
  unit_price: string
  vat_rate: string
  category?: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface ContractItem {
  id: string
  contract_id: string
  article_id?: string
  quantity: string
  override_price?: string
  override_vat_rate?: string
  description_override?: string
  billing_period: BillingPeriod
  sort_order: number
  is_active: boolean
  valid_from?: string
  valid_until?: string
  created_at: string
  updated_at: string
}

export interface Contract {
  id: string
  contract_number: string
  customer_id: string
  property_ref?: string
  start_date?: string
  end_date?: string
  billing_day: number
  payment_terms_days: number
  notes?: string
  status: ContractStatus
  created_by?: string
  items: ContractItem[]
  created_at: string
  updated_at: string
}

export interface InvoiceItem {
  id: string
  invoice_id: string
  article_id?: string
  position: number
  description: string
  quantity: string
  unit?: string
  unit_price_net: string
  vat_rate: string
  total_net: string
  total_vat: string
  total_gross: string
}

export interface Invoice {
  id: string
  invoice_number: string
  contract_id?: string
  customer_id: string
  invoice_date: string
  due_date: string
  billing_period_from?: string
  billing_period_to?: string
  status: InvoiceStatus
  subtotal_net: string
  total_vat: string
  total_gross: string
  currency: string
  notes?: string
  internal_notes?: string
  pdf_path?: string
  generated_by?: string
  generation_run_id?: string
  sent_at?: string
  paid_at?: string
  cancelled_at?: string
  items: InvoiceItem[]
  created_at: string
  updated_at: string
}

export interface PaymentRun {
  id: string
  run_type: RunType
  status: RunStatus
  triggered_by?: string
  period_from?: string
  period_to?: string
  invoice_count?: number
  total_amount?: string
  file_path?: string
  error_message?: string
  started_at?: string
  completed_at?: string
  created_at: string
}

// ── Kreditoren ───────────────────────────────────────────────────────────────

export interface Creditor {
  id: string
  creditor_number: string
  company_name?: string
  first_name?: string
  last_name?: string
  address_line1?: string
  address_line2?: string
  postal_code?: string
  city?: string
  country_code: string
  email?: string
  phone?: string
  iban?: string
  bic?: string
  bank_name?: string
  account_holder?: string
  vat_id?: string
  tax_number?: string
  datev_account_number?: string
  payment_terms_days: number
  notes?: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CreditorListResponse {
  items: Creditor[]
  total: number
  page: number
  page_size: number
}

// ── Eingangsrechnungen ────────────────────────────────────────────────────────

export type IncomingInvoiceStatus = 'open' | 'approved' | 'scheduled' | 'paid' | 'rejected' | 'cancelled'

export interface CreditorShort {
  id: string
  creditor_number: string
  company_name?: string
  first_name?: string
  last_name?: string
}

export interface IncomingInvoice {
  id: string
  document_number: string
  external_invoice_number?: string
  creditor_id: string
  creditor?: CreditorShort
  invoice_date: string
  receipt_date?: string
  due_date?: string
  total_net: string
  total_vat: string
  total_gross: string
  currency: string
  description?: string
  cost_account?: string
  status: IncomingInvoiceStatus
  approved_by?: string
  approved_at?: string
  paid_at?: string
  document_path?: string
  notes?: string
  created_at: string
  updated_at: string
}

export interface IncomingInvoiceListResponse {
  items: IncomingInvoice[]
  total: number
  page: number
  page_size: number
}

// ── Belege ────────────────────────────────────────────────────────────────────

export type ExpenseReceiptStatus = 'submitted' | 'approved' | 'paid' | 'rejected'

export interface UserShort {
  id: string
  full_name: string
  email: string
}

export interface ExpenseReceipt {
  id: string
  receipt_number: string
  submitted_by: string
  submitter?: UserShort
  approver?: UserShort
  receipt_date: string
  merchant?: string
  amount_gross: string
  vat_amount: string
  amount_net: string
  vat_rate: string
  category?: string
  description?: string
  payment_method?: string
  reimbursement_iban?: string
  reimbursement_account_holder?: string
  status: ExpenseReceiptStatus
  approved_by?: string
  approved_at?: string
  paid_at?: string
  document_path?: string
  notes?: string
  created_at: string
  updated_at: string
}

export interface ExpenseReceiptListResponse {
  items: ExpenseReceipt[]
  total: number
  page: number
  page_size: number
}

export interface CompanySettings {
  company_name: string
  company_street: string
  company_zip: string
  company_city: string
  company_country: string
  company_phone?: string
  company_email?: string
  company_vat_id?: string
  company_tax_number?: string
  company_iban?: string
  company_bic?: string
  company_bank_name?: string
  invoice_number_prefix: string
  invoice_number_year_reset: boolean
}
