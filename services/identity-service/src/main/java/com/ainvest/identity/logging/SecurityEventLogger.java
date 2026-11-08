package com.ainvest.identity.logging;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.stereotype.Component;

import java.util.UUID;

// one place that writes authentication events (login, register, token refresh - success and failure).
// The fields use Elastic Common Schema names (event.action, event.outcome, user.id ...), and with
// logging.structured.format.file=ecs each event becomes one JSON line that a SIEM can parse and correlate.
// Never logged: passwords, access or refresh tokens, the full e-mail address.
@Component
public class SecurityEventLogger {

    // separate logger name, so security events can be filtered or routed on their own
    private static final Logger log = LoggerFactory.getLogger("SECURITY");

    public void loginSucceeded(UUID userId, String email) {
        write("user-login", "success", userId, email, null);
    }

    // reason stays internal (e.g. unknown-email vs wrong-password): the API answers the same 401 for both,
    // but the difference matters when someone is guessing which e-mail addresses exist
    public void loginFailed(String email, String reason) {
        write("user-login", "failure", null, email, reason);
    }

    public void registered(UUID userId, String email) {
        write("user-register", "success", userId, email, null);
    }

    public void registrationRejected(String email, String reason) {
        write("user-register", "failure", null, email, reason);
    }

    public void refreshSucceeded(UUID userId) {
        write("token-refresh", "success", userId, null, null);
    }

    // an unknown refresh token is often an old, already rotated one being replayed - a sign the token was stolen
    public void refreshRejected(String reason) {
        write("token-refresh", "failure", null, null, reason);
    }

    private void write(String action, String outcome, UUID userId, String email, String reason) {
        String maskedEmail = mask(email);
        // MDC values are added to this log line only (closed again at the end of the try block)
        try (MDC.MDCCloseable category = MDC.putCloseable("event.category", "authentication");
             MDC.MDCCloseable eventAction = MDC.putCloseable("event.action", action);
             MDC.MDCCloseable eventOutcome = MDC.putCloseable("event.outcome", outcome);
             MDC.MDCCloseable user = userId == null ? null : MDC.putCloseable("user.id", userId.toString());
             MDC.MDCCloseable userEmail = maskedEmail == null ? null : MDC.putCloseable("user.email", maskedEmail);
             MDC.MDCCloseable eventReason = reason == null ? null : MDC.putCloseable("event.reason", reason)) {

            String message = "Security event: " + action + " " + outcome
                    + (maskedEmail == null ? "" : " for " + maskedEmail)
                    + (reason == null ? "" : " (" + reason + ")");
            if ("failure".equals(outcome)) {
                log.warn(message);
            } else {
                log.info(message);
            }
        }
    }

    // "aykut@gmail.com" -> "a***@gmail.com": enough to follow one account's events, without storing the
    // full personal identifier in every log line (data minimisation, KVKK)
    static String mask(String email) {
        if (email == null || email.isBlank()) {
            return null;
        }
        int at = email.indexOf('@');
        if (at <= 0) {
            return "***";
        }
        return email.charAt(0) + "***" + email.substring(at);
    }
}
