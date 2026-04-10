import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"
import { format, parseISO } from "date-fns"
import { de } from "date-fns/locale"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(dateStr: string | undefined | null): string {
  if (!dateStr) return "–"
  try {
    return format(parseISO(dateStr), "dd.MM.yyyy", { locale: de })
  } catch {
    return dateStr
  }
}

export function formatDateTime(dateStr: string | undefined | null): string {
  if (!dateStr) return "–"
  try {
    return format(parseISO(dateStr), "dd.MM.yyyy HH:mm", { locale: de })
  } catch {
    return dateStr
  }
}

export function formatCurrency(amount: string | number | undefined | null): string {
  if (amount === undefined || amount === null) return "–"
  const num = typeof amount === "string" ? parseFloat(amount) : amount
  return new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
  }).format(num)
}

export function formatNumber(
  value: string | number | undefined | null,
  decimals = 2
): string {
  if (value === undefined || value === null) return "–"
  const num = typeof value === "string" ? parseFloat(value) : value
  return new Intl.NumberFormat("de-DE", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(num)
}

export const INVOICE_STATUS_LABELS: Record<string, string> = {
  draft: "Entwurf",
  issued: "Ausgestellt",
  sent: "Versendet",
  paid: "Bezahlt",
  overdue: "Überfällig",
  cancelled: "Storniert",
}

export const INVOICE_STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700",
  issued: "bg-blue-100 text-blue-700",
  sent: "bg-indigo-100 text-indigo-700",
  paid: "bg-green-100 text-green-700",
  overdue: "bg-red-100 text-red-700",
  cancelled: "bg-orange-100 text-orange-700",
}

export const CONTRACT_STATUS_LABELS: Record<string, string> = {
  active: "Aktiv",
  terminated: "Gekündigt",
  suspended: "Ausgesetzt",
}

export const BILLING_PERIOD_LABELS: Record<string, string> = {
  monthly: "Monatlich",
  quarterly: "Vierteljährlich",
  annual: "Jährlich",
  "one-time": "Einmalig",
}
