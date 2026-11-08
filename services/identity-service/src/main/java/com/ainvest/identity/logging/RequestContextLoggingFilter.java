package com.ainvest.identity.logging;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.MDC;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.regex.Pattern;

// adds "who is calling" to every log line written while a request is handled (including the security events):
// the client IP and the gateway's correlation id, so one request can be followed from the gateway into Identity
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class RequestContextLoggingFilter extends OncePerRequestFilter {

    static final String CORRELATION_HEADER = "X-Correlation-ID";

    // same rule as the gateway: only id-like values reach the logs (no log injection through this header)
    private static final Pattern SAFE_ID = Pattern.compile("^[A-Za-z0-9._-]{1,64}$");

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        // behind the gateway this is the real client IP: server.forward-headers-strategy=native lets Tomcat take it
        // from X-Forwarded-For, but only when the request comes from a trusted local proxy (the gateway)
        MDC.put("source.ip", request.getRemoteAddr());

        String correlationId = request.getHeader(CORRELATION_HEADER);
        if (correlationId != null && SAFE_ID.matcher(correlationId).matches()) {
            MDC.put("correlation.id", correlationId);
        }

        try {
            chain.doFilter(request, response);
        } finally {
            // the thread goes back to the pool and must not carry this request's values into the next one
            MDC.remove("source.ip");
            MDC.remove("correlation.id");
        }
    }
}
