package com.ainvest.marketdata.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.time.Duration;

@Configuration
public class FxClientConfig {

    // the HTTP client for the FX provider; the timeouts are the first protection: without them a hanging
    // provider would block the request thread for as long as the operating system allows
    @Bean
    // (the injected builder comes from Spring Boot, so JSON uses Boot's ObjectMapper: dates, unknown fields ignored)
    public RestClient fxRestClient(RestClient.Builder builder,
                                   @Value("${market-data.fx.base-url}") String baseUrl,
                                   @Value("${market-data.fx.connect-timeout}") Duration connectTimeout,
                                   @Value("${market-data.fx.read-timeout}") Duration readTimeout) {
        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(connectTimeout);
        requestFactory.setReadTimeout(readTimeout);

        return builder
                .baseUrl(baseUrl)
                .requestFactory(requestFactory)
                .build();
    }
}
