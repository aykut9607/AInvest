// tr-TR formatting, the same conventions as the AI service (services/ai-rag-service/core/fmt.py):
// 12500 -> "12.500", 4.25 -> "4,25", whole lira with "TL" after the number, the percent sign first ("%18").

const LOCALE = "tr-TR";
const TIME_ZONE = "Europe/Istanbul";

export function formatNumber(value: number, maximumFractionDigits = 0): string {
  return value.toLocaleString(LOCALE, { maximumFractionDigits, minimumFractionDigits: 0 });
}

// whole lira by default: 12500.4 -> "12.500 TL"
export function formatMoney(value: number, maximumFractionDigits = 0): string {
  return `${formatNumber(value, maximumFractionDigits)} TL`;
}

// prices in another currency (4.4 screens): 4152.5 -> "4.152,5 USD"
export function formatPrice(value: number, currency = "USD", maximumFractionDigits = 2): string {
  return `${formatNumber(value, maximumFractionDigits)} ${currency}`;
}

// 18 -> "%18"; ratio=true takes 0.184 -> "%18,4" (with one fraction digit)
export function formatPercent(value: number, { ratio = false, fractionDigits = 0 } = {}): string {
  const percent = ratio ? value * 100 : value;
  return `%${formatNumber(percent, fractionDigits)}`;
}

function toDate(value: string | Date): Date | null {
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

// "24 Kasım 2026"
export function formatDate(value: string | Date): string {
  const date = toDate(value);
  return date ? date.toLocaleDateString(LOCALE, { day: "numeric", month: "long", year: "numeric", timeZone: TIME_ZONE }) : "";
}

// "24.11.2026" (compact, chart axes and tables)
export function formatShortDate(value: string | Date): string {
  const date = toDate(value);
  return date ? date.toLocaleDateString(LOCALE, { day: "2-digit", month: "2-digit", year: "numeric", timeZone: TIME_ZONE }) : "";
}

// "24 Kasım 2026 14:05"
export function formatDateTime(value: string | Date): string {
  const date = toDate(value);
  return date
    ? date.toLocaleString(LOCALE, {
        day: "numeric",
        month: "long",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: TIME_ZONE,
      })
    : "";
}

// signed change: 5 -> "+5", -3 -> "−3" (minus sign), 0 -> "0"
export function formatSigned(value: number, maximumFractionDigits = 0): string {
  if (value > 0) return `+${formatNumber(value, maximumFractionDigits)}`;
  if (value < 0) return `−${formatNumber(Math.abs(value), maximumFractionDigits)}`;
  return "0";
}

// ---- amount inputs (digits only) -----------------------------------------------------------------------------------

// 15 digits = up to 999,999,999,999,999, the most the Finance Profile column (numeric(18,2)) stores. Not a scoring
// limit: very large amounts are accepted and handled by the IQ rules.
export const AMOUNT_MAX_DIGITS = 15;

// keeps digits only, so "30.000" or "30,000" becomes "30000"; trims leading zeros and caps the length
export function toDigits(text: string, maxDigits = AMOUNT_MAX_DIGITS): string {
  return text.replace(/\D/g, "").replace(/^0+(?=\d)/, "").slice(0, maxDigits);
}

// "1234567" -> "1.234.567" (string based, exact for 15 digits)
export function groupDigits(digits: string): string {
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

// a saved 1250.50 (possible from the API) is shown as "1251": the form keeps whole numbers only
export function wholeAmountDigits(value: number): string {
  return Number.isFinite(value) && value > 0 ? String(Math.round(value)) : "";
}
