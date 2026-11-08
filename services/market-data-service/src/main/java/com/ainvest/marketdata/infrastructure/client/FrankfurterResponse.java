package com.ainvest.marketdata.infrastructure.client;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.Map;

// the provider's JSON, e.g. {"amount":1.0,"base":"USD","date":"2026-11-06","rates":{"TRY":50.153}}
public record FrankfurterResponse(BigDecimal amount, String base, LocalDate date, Map<String, BigDecimal> rates) {
}
