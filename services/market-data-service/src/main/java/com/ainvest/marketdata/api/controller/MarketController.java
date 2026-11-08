package com.ainvest.marketdata.api.controller;

import com.ainvest.marketdata.api.dto.FxRateResponse;
import com.ainvest.marketdata.domain.service.MarketDataService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/market")
public class MarketController {

    private final MarketDataService marketDataService;

    public MarketController(MarketDataService marketDataService) {
        this.marketDataService = marketDataService;
    }

    // GET /api/market/fx?base=USD&symbol=TRY  ->  {"base":"USD","symbol":"TRY","rate":50.153,"date":"2026-11-06",...}
    @GetMapping("/fx")
    public FxRateResponse getFxRate(@RequestParam(defaultValue = "USD") String base,
                                    @RequestParam(defaultValue = "TRY") String symbol) {
        return FxRateResponse.from(marketDataService.getFxRate(base, symbol));
    }
}
