package com.ainvest.identity.logging;

import ch.qos.logback.classic.Level;
import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;

import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

// what one security event looks like: the ECS fields a SIEM reads, the masked e-mail, and nothing left behind
class SecurityEventLoggerTest {

    private final SecurityEventLogger securityEvents = new SecurityEventLogger();
    private final ListAppender<ILoggingEvent> captured = new ListAppender<>();
    private Logger securityLogger;

    @BeforeEach
    void attachAppender() {
        securityLogger = (Logger) LoggerFactory.getLogger("SECURITY");
        captured.start();
        securityLogger.addAppender(captured);
    }

    @AfterEach
    void detachAppender() {
        securityLogger.detachAppender(captured);
    }

    @Test
    void failedLogin_IsAWarning_WithEcsFields_AndAMaskedEmail() {
        securityEvents.loginFailed("aykut@gmail.com", "wrong-password");

        ILoggingEvent event = captured.list.getFirst();
        Map<String, String> fields = event.getMDCPropertyMap();
        assertEquals(Level.WARN, event.getLevel());
        assertEquals("authentication", fields.get("event.category"));
        assertEquals("user-login", fields.get("event.action"));
        assertEquals("failure", fields.get("event.outcome"));
        assertEquals("wrong-password", fields.get("event.reason"));
        assertEquals("a***@gmail.com", fields.get("user.email"));
        // the full address appears neither in the fields nor in the message
        assertFalse(event.getFormattedMessage().contains("aykut@gmail.com"));
        assertFalse(fields.containsValue("aykut@gmail.com"));
    }

    @Test
    void successfulLogin_IsInfo_WithTheUserId() {
        UUID userId = UUID.randomUUID();

        securityEvents.loginSucceeded(userId, "aykut@gmail.com");

        ILoggingEvent event = captured.list.getFirst();
        assertEquals(Level.INFO, event.getLevel());
        assertEquals("success", event.getMDCPropertyMap().get("event.outcome"));
        assertEquals(userId.toString(), event.getMDCPropertyMap().get("user.id"));
        assertFalse(event.getMDCPropertyMap().containsKey("event.reason"));
    }

    @Test
    void eventFields_DoNotLeakIntoTheNextLogLine() {
        securityEvents.refreshRejected("expired-token");

        assertNull(MDC.get("event.action"));
        assertNull(MDC.get("event.reason"));
    }

    @Test
    void mask_KeepsFirstLetterAndDomainOnly() {
        assertEquals("a***@gmail.com", SecurityEventLogger.mask("aykut@gmail.com"));
        assertEquals("***", SecurityEventLogger.mask("not-an-email"));
        assertNull(SecurityEventLogger.mask(null));
        assertNull(SecurityEventLogger.mask(" "));
    }
}
