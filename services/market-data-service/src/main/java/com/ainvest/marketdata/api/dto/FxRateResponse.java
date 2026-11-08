package com.ainvest.marketdata.api.dto;

import com.ainvest.marketdata.domain.model.FxQuote;

import java.math.BigDecimal;
import java.time.LocalDate;

public record FxRateResponse(String base, String symbol, BigDecimal rate, LocalDate date, String source) {

    public static final String SOURCE = "frankfurter (ECB reference rates)";

    public static FxRateResponse from(FxQuote quote) {
        return new FxRateResponse(quote.base(), quote.symbol(), quote.rate(), quote.date(), SOURCE);
    }
}
