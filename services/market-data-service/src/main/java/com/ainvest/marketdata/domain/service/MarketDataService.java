package com.ainvest.marketdata.domain.service;

import com.ainvest.marketdata.domain.model.FxQuote;
import com.ainvest.marketdata.exception.InvalidCurrencyException;
import com.ainvest.marketdata.infrastructure.client.FxRateClient;
import org.springframework.stereotype.Service;

import java.util.Locale;
import java.util.regex.Pattern;

@Service
public class MarketDataService {

    // ISO 4217 style code: exactly 3 letters, e.g. USD, TRY, EUR
    private static final Pattern CURRENCY_CODE = Pattern.compile("^[A-Z]{3}$");

    private final FxRateClient fxRateClient;

    public MarketDataService(FxRateClient fxRateClient) {
        this.fxRateClient = fxRateClient;
    }

    public FxQuote getFxRate(String base, String symbol) {
        String normalizedBase = normalize(base);
        String normalizedSymbol = normalize(symbol);

        // checked here, before any outside call: a bad input must not cost a network round trip or a retry
        if (!CURRENCY_CODE.matcher(normalizedBase).matches() || !CURRENCY_CODE.matcher(normalizedSymbol).matches()) {
            throw new InvalidCurrencyException("Currency codes must be 3 letters, e.g. base=USD&symbol=TRY.");
        }
        if (normalizedBase.equals(normalizedSymbol)) {
            throw new InvalidCurrencyException("Base and symbol must be different currencies.");
        }
        return fxRateClient.fetchRate(normalizedBase, normalizedSymbol);
    }

    private static String normalize(String code) {
        return code == null ? "" : code.trim().toUpperCase(Locale.ROOT);
    }
}
