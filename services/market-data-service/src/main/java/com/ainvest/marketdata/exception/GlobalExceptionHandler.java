package com.ainvest.marketdata.exception;

import com.ainvest.marketdata.api.dto.ErrorResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(InvalidCurrencyException.class)
    public ResponseEntity<ErrorResponse> handleInvalidCurrency(InvalidCurrencyException ex) {
        return ResponseEntity.badRequest().body(new ErrorResponse(ex.getMessage()));
    }

    // 503 + Retry-After: the caller did nothing wrong, the outside provider is down - try again later.
    // (In .NET we answer 502 for a failing internal service; here the data source itself is temporarily unavailable.)
    @ExceptionHandler(MarketDataUnavailableException.class)
    public ResponseEntity<ErrorResponse> handleUnavailable(MarketDataUnavailableException ex) {
        log.warn("FX rate unavailable: {} (cause: {})", ex.getMessage(),
                ex.getCause() == null ? "none" : ex.getCause().getClass().getSimpleName());
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                .header(HttpHeaders.RETRY_AFTER, "15")
                .body(new ErrorResponse(ex.getMessage()));
    }
}
