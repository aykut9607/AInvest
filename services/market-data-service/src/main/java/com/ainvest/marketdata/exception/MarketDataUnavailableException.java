package com.ainvest.marketdata.exception;

// the FX provider could not be reached or gave no usable answer, even after the retries (or the circuit is open)
public class MarketDataUnavailableException extends RuntimeException {

    public MarketDataUnavailableException(String message, Throwable cause) {
        super(message, cause);
    }
}
