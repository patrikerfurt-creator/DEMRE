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

/** Schlägt den BIC anhand der IBAN über die openiban.com-API nach. */
export async function lookupBicFromIban(iban: string): Promise<string | null> {
  const clean = iban.replace(/\s/g, '').toUpperCase()
  if (!validateIban(clean)) return null
  try {
    const res = await fetch(`https://openiban.com/validate/${clean}?getBIC=true`)
    if (!res.ok) return null
    const data = await res.json()
    return (data?.bankData?.bic as string) || null
  } catch {
    return null
  }
}

/** Prüft eine IBAN per ISO-7064-Prüfsumme (Mod-97). Leerzeichen werden ignoriert. */
export function validateIban(raw: string): boolean {
  const iban = raw.replace(/\s/g, '').toUpperCase()
  if (!/^[A-Z]{2}[0-9]{2}[A-Z0-9]{1,30}$/.test(iban)) return false
  const rearranged = iban.slice(4) + iban.slice(0, 4)
  const numeric = rearranged
    .split('')
    .map((c) => {
      const code = c.charCodeAt(0)
      return code >= 65 ? String(code - 55) : c
    })
    .join('')
  let remainder = 0
  for (const ch of numeric) {
    remainder = (remainder * 10 + parseInt(ch, 10)) % 97
  }
  return remainder === 1
}
