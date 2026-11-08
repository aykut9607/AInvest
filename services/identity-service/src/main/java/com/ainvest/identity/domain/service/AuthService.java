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
import com.ainvest.identity.logging.SecurityEventLogger;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.Base64;

@Service
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;
    private final SecurityEventLogger securityEvents;

    @Value("${jwt.refresh-token-expiration-ms}")
    private long refreshTokenExpirationMs;

    public AuthService(UserRepository userRepository, PasswordEncoder passwordEncoder, JwtService jwtService,
                       SecurityEventLogger securityEvents) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtService = jwtService;
        this.securityEvents = securityEvents;
    }

    public AuthResponse register(RegisterRequest request) {
        if (userRepository.findByEmail(request.email()).isPresent()) {
            securityEvents.registrationRejected(request.email(), "email-already-registered");
            throw new EmailAlreadyExistsException(request.email());
        }

        User user = new User();
        user.setEmail(request.email());
        user.setPasswordHash(passwordEncoder.encode(request.password()));
        user.setCreatedAt(Instant.now());
        String rawRefreshToken = issueNewRefreshToken(user);

        userRepository.save(user);
        securityEvents.registered(user.getId(), user.getEmail());

        String accessToken = jwtService.generateAccessToken(user.getId(), user.getEmail(), user.getRole());
        return new AuthResponse(accessToken, rawRefreshToken);
    }

    public AuthResponse login(LoginRequest request) {
        User user = userRepository.findByEmail(request.email()).orElse(null);
        if (user == null) {
            securityEvents.loginFailed(request.email(), "unknown-email");
            throw new InvalidCredentialsException();
        }

        if (!passwordEncoder.matches(request.password(), user.getPasswordHash())) {
            securityEvents.loginFailed(request.email(), "wrong-password");
            throw new InvalidCredentialsException();
        }

        String rawRefreshToken = issueNewRefreshToken(user);
        userRepository.save(user);
        securityEvents.loginSucceeded(user.getId(), user.getEmail());

        String accessToken = jwtService.generateAccessToken(user.getId(), user.getEmail(), user.getRole());
        return new AuthResponse(accessToken, rawRefreshToken);
    }

    public AuthResponse refresh(RefreshRequest request) {
        String incomingHash = hashToken(request.refreshToken());

        User user = userRepository.findByRefreshTokenHash(incomingHash).orElse(null);
        if (user == null) {
            securityEvents.refreshRejected("unknown-or-already-rotated-token");
            throw new InvalidRefreshTokenException();
        }

        if (user.getRefreshTokenExpiry() == null || Instant.now().isAfter(user.getRefreshTokenExpiry())) {
            securityEvents.refreshRejected("expired-token");
            throw new InvalidRefreshTokenException();
        }

        String rawRefreshToken = issueNewRefreshToken(user);
        userRepository.save(user);
        securityEvents.refreshSucceeded(user.getId());

        String accessToken = jwtService.generateAccessToken(user.getId(), user.getEmail(), user.getRole());
        return new AuthResponse(accessToken, rawRefreshToken);
    }

    // returns the raw token instead of keeping it in a field: this service is a singleton shared by all
    // requests, so a field would let two concurrent logins swap each other's refresh tokens
    private String issueNewRefreshToken(User user) {
        String rawRefreshToken = generateRawRefreshToken();
        user.setRefreshTokenHash(hashToken(rawRefreshToken));
        user.setRefreshTokenExpiry(Instant.now().plusMillis(refreshTokenExpirationMs));
        return rawRefreshToken;
    }

    private String generateRawRefreshToken() {
        SecureRandom secureRandom = new SecureRandom();
        byte[] randomBytes = new byte[32];
        secureRandom.nextBytes(randomBytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(randomBytes);
    }

    private String hashToken(String rawToken) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(rawToken.getBytes(StandardCharsets.UTF_8));
            return Base64.getEncoder().encodeToString(hash);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 not available", e);
        }
    }
}