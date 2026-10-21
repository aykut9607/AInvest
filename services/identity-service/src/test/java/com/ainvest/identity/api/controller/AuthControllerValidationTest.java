package com.ainvest.identity.api.controller;

import com.ainvest.identity.api.dto.AuthResponse;
import com.ainvest.identity.config.SecurityConfig;
import com.ainvest.identity.domain.service.AuthService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

// web layer only: real controller, real security config and real GlobalExceptionHandler; AuthService is mocked
@WebMvcTest(AuthController.class)
@Import(SecurityConfig.class)
class AuthControllerValidationTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private AuthService authService;

    private ResultActions postJson(String path, String body) throws Exception {
        return mockMvc.perform(post(path).contentType(MediaType.APPLICATION_JSON).content(body));
    }

    @Test
    void register_WithValidInput_Returns200() throws Exception {
        when(authService.register(any())).thenReturn(new AuthResponse("access", "refresh"));

        postJson("/auth/register", """
                {"email":"demo@ainvest.dev","password":"Demo12345"}""")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.accessToken").value("access"));
    }

    @Test
    void register_WithBlankEmail_Returns400_AndNeverReachesService() throws Exception {
        postJson("/auth/register", """
                {"email":"","password":"Demo12345"}""")
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Email is required"));

        verify(authService, never()).register(any());
    }

    @Test
    void register_WithInvalidEmail_Returns400() throws Exception {
        postJson("/auth/register", """
                {"email":"not-an-email","password":"Demo12345"}""")
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Email must be a valid email address"));
    }

    @Test
    void register_WithShortPassword_Returns400() throws Exception {
        postJson("/auth/register", """
                {"email":"demo@ainvest.dev","password":"a"}""")
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Password must be between 8 and 72 characters"));
    }

    @Test
    void register_WithTooLongPassword_Returns400() throws Exception {
        String longPassword = "x".repeat(73);
        postJson("/auth/register", "{\"email\":\"demo@ainvest.dev\",\"password\":\"" + longPassword + "\"}")
                .andExpect(status().isBadRequest());
    }

    @Test
    void login_WithBlankPassword_Returns400() throws Exception {
        postJson("/auth/login", """
                {"email":"demo@ainvest.dev","password":""}""")
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Password is required"));
    }

    @Test
    void login_WithShortButNonBlankPassword_ReachesService() throws Exception {
        // no length rule on login, so older accounts are not locked out
        when(authService.login(any())).thenReturn(new AuthResponse("access", "refresh"));

        postJson("/auth/login", """
                {"email":"demo@ainvest.dev","password":"a"}""")
                .andExpect(status().isOk());
    }

    @Test
    void refresh_WithBlankToken_Returns400() throws Exception {
        postJson("/auth/refresh", """
                {"refreshToken":"  "}""")
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Refresh token is required"));
    }

    @Test
    void malformedJson_Returns400_WithOurErrorFormat() throws Exception {
        postJson("/auth/login", "{not json")
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Request body is missing or malformed"));
    }
}
