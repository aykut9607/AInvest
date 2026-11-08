package com.ainvest.marketdata.api.dto;

// same error shape as Identity: {"message": "..."}
public record ErrorResponse(String message) {
}
