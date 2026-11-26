// Turkish wording for the assistant screen. Intent codes: services/ai-rag-service/services/assistant.py (INTENTS,
// _TOOL_INTENT); suggested questions: evaluation/playground.py (QUESTIONS, without the attack examples).
import type { AskResponse } from "../../types/api";

export const INTENT_LABELS: Record<string, string> = {
  PROFILE_SUMMARY: "Genel durum",
  INCOME_EXPENSE: "Gelir ve gider",
  DEBT: "Borç",
  INVESTMENT: "Yatırım",
  CASH_RESERVE: "Nakit rezervi",
  SAVINGS: "Tasarruf",
  IQ_SCORE: "Finansal IQ",
  IQ_TREND: "Skor geçmişi",
  WARNINGS: "Uyarılar",
  PORTFOLIO: "Portföy",
  FAQ: "Sık sorulan",
  MARKET_PRICE: "Piyasa fiyatı",
  OTHER: "Konu dışı",
};

// an intent (or tool name) this app does not know yet is shown as it came
export function intentLabel(code: string): string {
  return INTENT_LABELS[code] ?? code;
}

export const SUGGESTED_QUESTIONS = [
  "Kaç para borcum var?",
  "Ayda ne kadar para artıyor?",
  "Acil durum fonum kaç ay yeter?",
  "Finansal IQ skorum kaç?",
  "Skorum zaman içinde nasıl değişti?",
  "Bu şekilde devam edersem bir risk var mı?",
  "Önerilen portföyde altına ne kadar ayrıldı?",
  "Finansal IQ nedir?",
  "Neden risk tercihimi sormuyorsunuz?",
  "BTC kaç dolar?",
];

export const MODE_LABELS: Record<AskResponse["mode"], string> = {
  router: "Yönlendirici (router)",
  tools: "Araç çağırma (tools)",
};

export interface AnswerNote {
  tone: "info" | "warning";
  text: string;
}

// a friendly line under answers that are not the model's free text on purpose
export function answerNote(response: AskResponse): AnswerNote | null {
  if (response.fallbackReason === "BLOCKED_INPUT") {
    return {
      tone: "warning",
      text:
        "Bu soru güvenlik filtresine takıldı. Asistan yalnızca kendi finansal verilerin, Finansal IQ'n ve uygulama " +
        "hakkındaki soruları cevaplar; talimatlarını değiştirmeye ya da başka kullanıcıların verisine ulaşmaya " +
        "çalışan istekleri işlemez. Sorunu farklı sözcüklerle yeniden sorabilirsin.",
    };
  }
  if (response.fallbackReason === "DATA_UNAVAILABLE") {
    return {
      tone: "warning",
      text: "Profil ve Finansal IQ verilerine şu an ulaşılamadı. Biraz sonra yeniden dene.",
    };
  }
  if (response.intents.includes("MARKET_PRICE")) {
    return {
      tone: "info",
      text: "Asistan piyasa fiyatlarını (kripto, hisse, döviz, altın) henüz göremiyor. Kural tabanlı piyasa planları için Piyasa (4.4) sayfasına bak.",
    };
  }
  return null;
}

const TIME = new Intl.DateTimeFormat("tr-TR", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Istanbul" });

// "14:05"
export function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : TIME.format(date);
}
