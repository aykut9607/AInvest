package com.ainvest.marketdata.infrastructure.client;

import com.ainvest.marketdata.domain.model.FxQuote;
import com.ainvest.marketdata.exception.InvalidCurrencyException;
import com.ainvest.marketdata.exception.MarketDataUnavailableException;
import io.github.resilience4j.circuitbreaker.CallNotPermittedException;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import io.github.resilience4j.retry.annotation.Retry;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClient;

import java.math.BigDecimal;

// the only class that talks to the FX provider. The two annotations wrap fetchRate in Resilience4j
// (settings under resilience4j.* in application.properties). Default order: Retry is the outer layer,
// CircuitBreaker the inner one - so every single attempt is counted by the breaker, and when the breaker
// is open the retry does not even try (CallNotPermittedException is on its ignore list).
// The annotations only work when fetchRate is called from another bean (they are applied by a Spring proxy).
@Component
public class FxRateClient {

    private final RestClient fxRestClient;

    public FxRateClient(RestClient fxRestClient) {
        this.fxRestClient = fxRestClient;
    }

    @Retry(name = "fxRates", fallbackMethod = "unavailable")
    @CircuitBreaker(name = "fxRates")
    public FxQuote fetchRate(String base, String symbol) {
        FrankfurterResponse response = fxRestClient.get()
                .uri(uri -> uri.path("/latest")
                        .queryParam("base", base)
                        .queryParam("symbols", symbol)
                        .build())
                .retrieve()
                .body(FrankfurterResponse.class);

        BigDecimal rate = response == null || response.rates() == null ? null : response.rates().get(symbol);
        if (rate == null) {
            throw new MarketDataUnavailableException("The FX provider returned no rate for " + base + "/" + symbol, null);
        }
        return new FxQuote(base, symbol, rate, response.date());
    }

    // fallback: runs once the retries are used up (or at once when the circuit is open) and turns the
    // technical failure into a clear answer for the caller instead of a 500 with a stack trace
    private FxQuote unavailable(String base, String symbol, Throwable cause) {
        if (cause instanceof MarketDataUnavailableException alreadyClear) {
            // e.g. "returned no rate" from fetchRate itself: keep its own message
            throw alreadyClear;
        }
        if (cause instanceof HttpClientErrorException) {
            // a 4xx from the provider means the request itself is wrong (e.g. a currency it does not know)
            throw new InvalidCurrencyException("Unknown currency pair " + base + "/" + symbol);
        }
        String reason = cause instanceof CallNotPermittedException
                ? "FX provider calls are paused after repeated failures (circuit open)"
                : "FX provider is unavailable";
        throw new MarketDataUnavailableException(reason, cause);
    }
}
