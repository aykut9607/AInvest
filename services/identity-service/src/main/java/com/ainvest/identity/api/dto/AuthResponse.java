package com.ainvest.identity.api.dto;

public record AuthResponse(String accessToken, String refreshToken) {
}