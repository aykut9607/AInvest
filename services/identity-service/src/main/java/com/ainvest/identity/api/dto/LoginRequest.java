package com.ainvest.identity.api.dto;

import jakarta.validation.constraints.NotBlank;

// login only checks presence: length rules here would lock out older accounts and hint the password policy
public record LoginRequest(
        @NotBlank(message = "Email is required")
        String email,

        @NotBlank(message = "Password is required")
        String password) {
}
