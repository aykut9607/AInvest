package com.ainvest.marketdata;

import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.circuitbreaker.CircuitBreakerRegistry;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.io.IOException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.containsString;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

// the real Spring app with the real Resilience4j settings, only the FX provider is fake and the waits are short
@SpringBootTest(properties = {
        "market-data.fx.read-timeout=300ms",
        "resilience4j.retry.instances.fxRates.wait-duration=10ms"
})
@AutoConfigureMockMvc
class FxRateResilienceTest {

    private static final FakeFxProvider provider = createProvider();

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private CircuitBreakerRegistry circuitBreakerRegistry;

    @DynamicPropertySource
    static void pointToFakeProvider(DynamicPropertyRegistry registry) {
        registry.add("market-data.fx.base-url", provider::baseUrl);
    }

    @BeforeEach
    void cleanState() {
        provider.reset();
        // the breaker lives for the whole test context; each test starts with a closed one
        circuitBreakerRegistry.circuitBreaker("fxRates").reset();
    }

    @AfterAll
    static void stopProvider() {
        provider.stop();
    }

    @Test
    void returnsTheRateWhenTheProviderAnswers() throws Exception {
        mockMvc.perform(get("/api/market/fx").param("base", "usd").param("symbol", "try"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.base").value("USD"))
                .andExpect(jsonPath("$.symbol").value("TRY"))
                .andExpect(jsonPath("$.rate").value(50.153))
                .andExpect(jsonPath("$.date").value("2026-11-06"));

        assertThat(provider.hits()).isEqualTo(1);
    }

    @Test
    void retriesTemporaryErrorsAndThenSucceeds() throws Exception {
        provider.then(FakeFxProvider.status(503), FakeFxProvider.status(503), FakeFxProvider.ok());

        mockMvc.perform(get("/api/market/fx"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.rate").value(50.153));

        // 2 failed attempts + 1 successful one: the user never saw the two 503s
        assertThat(provider.hits()).isEqualTo(3);
    }

    @Test
    void givesUpAfterThreeAttemptsWith503() throws Exception {
        provider.always(FakeFxProvider.status(500));

        mockMvc.perform(get("/api/market/fx"))
                .andExpect(status().isServiceUnavailable())
                .andExpect(header().string("Retry-After", "15"))
                .andExpect(jsonPath("$.message").value("FX provider is unavailable"));

        assertThat(provider.hits()).isEqualTo(3);
    }

    @Test
    void doesNotRetryAClientError() throws Exception {
        // a 4xx means the request is wrong; asking again would give the same answer
        provider.always(FakeFxProvider.status(404));

        mockMvc.perform(get("/api/market/fx").param("base", "USD").param("symbol", "XYZ"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Unknown currency pair USD/XYZ"));

        assertThat(provider.hits()).isEqualTo(1);
    }

    @Test
    void rejectsABadCurrencyCodeWithoutCallingTheProvider() throws Exception {
        mockMvc.perform(get("/api/market/fx").param("base", "US1").param("symbol", "TRY"))
                .andExpect(status().isBadRequest());
        mockMvc.perform(get("/api/market/fx").param("base", "TRY").param("symbol", "TRY"))
                .andExpect(status().isBadRequest());

        assertThat(provider.hits()).isZero();
    }

    @Test
    void aSlowProviderTimesOutInsteadOfHanging() throws Exception {
        // the provider would answer after 2 s, the client waits at most 300 ms per attempt
        provider.always(FakeFxProvider.slow(2000));

        long start = System.nanoTime();
        mockMvc.perform(get("/api/market/fx"))
                .andExpect(status().isServiceUnavailable());
        long elapsedMillis = (System.nanoTime() - start) / 1_000_000;

        assertThat(provider.hits()).isEqualTo(3);
        // 3 x 300 ms + short waits; without the timeout this would take 3 x 2 s
        assertThat(elapsedMillis).isLessThan(2000);
    }

    @Test
    void circuitOpensAfterRepeatedFailuresAndStopsCallingTheProvider() throws Exception {
        provider.always(FakeFxProvider.status(500));

        // two failing requests = enough failed attempts (at least 5, all failed) to open the breaker
        mockMvc.perform(get("/api/market/fx")).andExpect(status().isServiceUnavailable());
        mockMvc.perform(get("/api/market/fx")).andExpect(status().isServiceUnavailable());

        CircuitBreaker breaker = circuitBreakerRegistry.circuitBreaker("fxRates");
        assertThat(breaker.getState()).isEqualTo(CircuitBreaker.State.OPEN);
        int hitsWhenOpened = provider.hits();

        // now the provider is not even called: the answer comes at once from the open breaker
        mockMvc.perform(get("/api/market/fx"))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.message").value(containsString("circuit open")));

        assertThat(provider.hits()).isEqualTo(hitsWhenOpened);
    }

    private static FakeFxProvider createProvider() {
        try {
            return new FakeFxProvider();
        } catch (IOException e) {
            throw new IllegalStateException("Could not start the fake FX provider", e);
        }
    }
}
