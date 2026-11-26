import { useEffect, useRef, useState } from "react";

export interface RateLimitNoticeProps {
  // from RateLimitError.retryAfterSeconds; give the component a new key (RateLimitError.retryAt) for a new error
  seconds: number;
  // wording with the remaining seconds; default: generic request limit
  message?: (secondsLeft: number) => string;
  // called once when the countdown reaches 0 (e.g. enable the button again)
  onDone?: () => void;
}

const defaultMessage = (s: number) => `Çok fazla istek gönderildi. ${s} saniye sonra tekrar deneyin.`;

// the gateway's 429 (login: 5 a minute per IP, /ai: 10 a minute per user) with a live countdown
export default function RateLimitNotice({ seconds, message = defaultMessage, onDone }: RateLimitNoticeProps) {
  const [left, setLeft] = useState(Math.max(0, Math.ceil(seconds)));
  const onDoneRef = useRef(onDone);

  useEffect(() => {
    onDoneRef.current = onDone;
  }, [onDone]);

  useEffect(() => {
    const deadline = Date.now() + Math.max(0, seconds) * 1000;
    const timer = setInterval(() => {
      const remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
      setLeft(remaining);
      if (remaining === 0) {
        clearInterval(timer);
        onDoneRef.current?.();
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [seconds]);

  return (
    <div className="notice notice-warning" role="status" aria-live="polite">
      <svg className="notice-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" strokeLinecap="round" />
      </svg>
      <div className="notice-body">
        <p>{left > 0 ? message(left) : "Şimdi tekrar deneyebilirsiniz."}</p>
      </div>
    </div>
  );
}
