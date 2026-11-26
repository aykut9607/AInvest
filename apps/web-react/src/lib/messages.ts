// The services answer in English (Identity, Finance Profile and Financial IQ Messages.cs, the AI service's own
// errors); the UI is Turkish. Known messages are translated here, anything unknown is shown as it came.

const EXACT: Record<string, string> = {
  // Identity (RegisterRequest/LoginRequest validation, GlobalExceptionHandler, AuthService)
  "Email is required": "E-posta adresi gerekli.",
  "Password is required": "Şifre gerekli.",
  "Email must be a valid email address": "Geçerli bir e-posta adresi girin.",
  "Email must be at most 255 characters": "E-posta adresi en fazla 255 karakter olabilir.",
  "Password must be between 8 and 72 characters": "Şifre 8 ile 72 karakter arasında olmalı.",
  "Request body is missing or malformed": "İstek eksik ya da hatalı gönderildi.",
  "Invalid email or password": "E-posta adresi veya şifre hatalı.",
  "Invalid or expired refresh token": "Oturumunuzun süresi doldu. Lütfen yeniden giriş yapın.",

  // Finance Profile (Messages.cs)
  "Financial profile not found.": "Kayıtlı finansal profil bulunamadı.",
  "Monthly income must be greater than zero.": "Aylık gelir sıfırdan büyük olmalı.",
  "Monetary fields cannot be negative.": "Tutarlar negatif olamaz.",
  "Monetary fields must be at most 999,999,999,999,999.": "Tutarlar en fazla 999.999.999.999.999 olabilir.",
  "Risk preference must be one of the allowed values.": "Risk tercihi geçerli değerlerden biri olmalı.",
  "Impatience level must be between 1 and 5.": "Sabırsızlık düzeyi 1 ile 5 arasında olmalı.",
  "User id is required and must be at most 100 characters.": "Kullanıcı kimliği gerekli ve en fazla 100 karakter olabilir.",
  "Financial IQ service is unavailable. Please try again later.":
    "Finansal IQ servisine şu anda ulaşılamıyor. Lütfen biraz sonra tekrar deneyin.",
  "Financial IQ service could not calculate the score.": "Finansal IQ servisi skoru hesaplayamadı.",
  "Financial IQ service returned an empty result.": "Finansal IQ servisi boş sonuç döndürdü.",
  "Monthly interest rate must be between 0 and 1 (0.035 = 3.5% a month).":
    "Aylık faiz oranı 0 ile 1 arasında olmalı (0,035 = ayda %3,5).",
  "Financial IQ service could not calculate the debt payoff.": "Finansal IQ servisi borç ödeme planını hesaplayamadı.",

  // Financial IQ (Messages.cs)
  "Financial IQ result not found.": "Henüz hesaplanmış bir Finansal IQ sonucu yok.",
  "No Financial IQ history found for this user.": "Henüz skor geçmişin yok.",
  "Take must be between 1 and 100.": "Kayıt sayısı 1 ile 100 arasında olmalı.",
  "There is no debt to pay off.": "Ödenecek borç yok.",
  "The monthly payment does not cover the monthly interest, so the debt never gets smaller.":
    "Aylık taksit aylık faizi karşılamıyor; bu yüzden borç hiç azalmıyor.",
  "The debt is not paid off within 600 months (50 years) with this payment.":
    "Bu taksitle borç 600 ay (50 yıl) içinde kapanmıyor.",
  "Scoring version not found.": "Skor kuralı sürümü bulunamadı.",

  // AI / RAG (main.py, api/deps.py)
  "Sign in first: this endpoint needs the gateway's token.": "Önce giriş yapın: bu istek oturum bilgisi gerektiriyor.",
  "The gateway refused the token for this data.": "Ağ geçidi bu veri için oturumunuzu kabul etmedi.",
  "User data is unavailable right now.": "Kullanıcı verilerine şu anda ulaşılamıyor.",
};

const PREFIX: [string, string][] = [
  // "Email already registered: someone@example.com"
  ["Email already registered", "Bu e-posta adresiyle kayıtlı bir hesap zaten var."],
];

function translateOne(message: string): string {
  const trimmed = message.trim();
  const exact = EXACT[trimmed] ?? EXACT[trimmed.replace(/\.$/, "")] ?? EXACT[`${trimmed}.`];
  if (exact) return exact;
  const prefix = PREFIX.find(([start]) => trimmed.startsWith(start));
  return prefix ? prefix[1] : trimmed;
}

// Identity joins several validation messages with "; " (sorted), so each part is translated on its own
export function translateServerMessage(message: string): string {
  const parts = message.split(/;\s*/).filter((part) => part.length > 0);
  if (parts.length <= 1) return translateOne(message);
  return parts.map(translateOne).join(" ");
}
