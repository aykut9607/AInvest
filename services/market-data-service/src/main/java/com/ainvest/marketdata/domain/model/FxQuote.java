package com.ainvest.marketdata.domain.model;

import java.math.BigDecimal;
import java.time.LocalDate;

// 1 unit of base = rate units of symbol, as published on date
public record FxQuote(String base, String symbol, BigDecimal rate, LocalDate date) {
}
