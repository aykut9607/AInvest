package com.ainvest.identity.domain.service;

import com.ainvest.identity.api.dto.AuthResponse;
import com.ainvest.identity.api.dto.LoginRequest;
import com.ainvest.identity.api.dto.RefreshRequest;
import com.ainvest.identity.api.dto.RegisterRequest;
import com.ainvest.identity.config.JwtService;
import com.ainvest.identity.domain.model.User;
import com.ainvest.identity.exception.EmailAlreadyExistsException;
import com.ainvest.identity.exception.InvalidCredentialsException;
import com.ainvest.identity.exception.InvalidRefreshTokenException;
import com.ainvest.identity.infrastructure.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

// plain unit tests: the repository is mocked, so no database is needed
class AuthServiceTest {

    private UserRepository userRepository;
    private AuthService authService;

    // the single "row" the mocked repository knows about
    private User storedUser;

    @BeforeEach
    void setUp() {
        userRepository = mock(UserRepository.class);

        JwtService jwtService = new JwtService();
        ReflectionTestUtils.setField(jwtService, "secret", "test-only-secret-key-that-is-long-enough-for-hs512-signing-1234567890");
        ReflectionTestUtils.setField(jwtService, "accessTokenExpirationMs", 900_000L);

        authService = new AuthService(userRepository, new BCryptPasswordEncoder(), jwtService);
        ReflectionTestUtils.setField(authService, "refreshTokenExpirationMs", 604_800_000L);

        // save() plays the database: assigns an id and remembers the user
        when(userRepository.save(any(User.class))).thenAnswer(invocation -> {
            User user = invocation.getArgument(0);
            if (user.getId() == null) user.setId(UUID.randomUUID());
            storedUser = user;
            return user;
        });
        when(userRepository.findByEmail(anyString())).thenAnswer(invocation ->
                storedUser != null && storedUser.getEmail().equals(invocation.getArgument(0))
                        ? Optional.of(storedUser) : Optional.empty());
        // only the hash that is currently stored on the user matches
        when(userRepository.findByRefreshTokenHash(anyString())).thenAnswer(invocation ->
                storedUser != null && invocation.getArgument(0).equals(storedUser.getRefreshTokenHash())
                        ? Optional.of(storedUser) : Optional.empty());
    }

    @Test
    void register_ReturnsTheRefreshTokenWhoseHashIsStored() {
        AuthResponse response = authService.register(new RegisterRequest("a@ainvest.dev", "Secret123"));

        assertNotNull(response.accessToken());
        // the returned token must be the one saved for this user, so refreshing with it works
        assertDoesNotThrow(() -> authService.refresh(new RefreshRequest(response.refreshToken())));
    }

    @Test
    void register_StoresHashNotRawToken() {
        AuthResponse response = authService.register(new RegisterRequest("a@ainvest.dev", "Secret123"));

        assertNotEquals(response.refreshToken(), storedUser.getRefreshTokenHash());
        assertNotEquals("Secret123", storedUser.getPasswordHash());
    }

    @Test
    void register_WithExistingEmail_Throws() {
        authService.register(new RegisterRequest("a@ainvest.dev", "Secret123"));

        assertThrows(EmailAlreadyExistsException.class,
                () -> authService.register(new RegisterRequest("a@ainvest.dev", "Other123")));
    }

    @Test
    void login_WithWrongPassword_Throws() {
        authService.register(new RegisterRequest("a@ainvest.dev", "Secret123"));

        assertThrows(InvalidCredentialsException.class,
                () -> authService.login(new LoginRequest("a@ainvest.dev", "wrong")));
    }

    @Test
    void login_IssuesANewRefreshToken_AndTheOldOneStopsWorking() {
        AuthResponse registered = authService.register(new RegisterRequest("a@ainvest.dev", "Secret123"));
        AuthResponse loggedIn = authService.login(new LoginRequest("a@ainvest.dev", "Secret123"));

        assertNotEquals(registered.refreshToken(), loggedIn.refreshToken());
        assertThrows(InvalidRefreshTokenException.class,
                () -> authService.refresh(new RefreshRequest(registered.refreshToken())));
        assertDoesNotThrow(() -> authService.refresh(new RefreshRequest(loggedIn.refreshToken())));
    }

    @Test
    void refresh_RotatesTheToken_SoReusingItFails() {
        AuthResponse registered = authService.register(new RegisterRequest("a@ainvest.dev", "Secret123"));

        AuthResponse refreshed = authService.refresh(new RefreshRequest(registered.refreshToken()));

        assertNotEquals(registered.refreshToken(), refreshed.refreshToken());
        assertThrows(InvalidRefreshTokenException.class,
                () -> authService.refresh(new RefreshRequest(registered.refreshToken())));
    }
}
