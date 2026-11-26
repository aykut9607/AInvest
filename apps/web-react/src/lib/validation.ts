// Client-side checks that mirror the Identity service (RegisterRequest / LoginRequest), to save a round trip.
// The server stays the authority: its messages are shown when it disagrees.

export const PASSWORD_MIN = 8;
export const PASSWORD_MAX = 72;
export const EMAIL_MAX = 255;

// Hibernate's @Email accepts "local@domain" without a dot, so this stays as loose: one @, no spaces
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+$/;

export function validateEmail(email: string): string | null {
  const value = email.trim();
  if (!value) return "E-posta adresi gerekli.";
  if (value.length > EMAIL_MAX) return `E-posta adresi en fazla ${EMAIL_MAX} karakter olabilir.`;
  if (!EMAIL_PATTERN.test(value)) return "Geçerli bir e-posta adresi girin.";
  return null;
}

export function validateLoginPassword(password: string): string | null {
  return password ? null : "Şifre gerekli.";
}

export function validateNewPassword(password: string): string | null {
  if (!password) return "Şifre gerekli.";
  if (password.length < PASSWORD_MIN || password.length > PASSWORD_MAX) {
    return `Şifre ${PASSWORD_MIN} ile ${PASSWORD_MAX} karakter arasında olmalı.`;
  }
  return null;
}
