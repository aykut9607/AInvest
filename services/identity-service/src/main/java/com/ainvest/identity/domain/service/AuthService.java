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

    @Value("${jwt.refresh-token-expiration-ms}")
    private long refreshTokenExpirationMs;

    public AuthService(UserRepository userRepository, PasswordEncoder passwordEncoder, JwtService jwtService) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtService = jwtService;
    }

    public AuthResponse register(RegisterRequest request) {
        if (userRepository.findByEmail(request.email()).isPresent()) {
            throw new EmailAlreadyExistsException(request.email());
        }

        User user = new User();
        user.setEmail(request.email());
        user.setPasswordHash(passwordEncoder.encode(request.password()));
        user.setCreatedAt(Instant.now());
        issueNewRefreshToken(user);

        userRepository.save(user);

        String accessToken = jwtService.generateAccessToken(user.getId(), user.getEmail(), user.getRole());
        return new AuthResponse(accessToken, currentRawRefreshToken);
    }

    public AuthResponse login(LoginRequest request) {
        User user = userRepository.findByEmail(request.email())
                .orElseThrow(InvalidCredentialsException::new);

        if (!passwordEncoder.matches(request.password(), user.getPasswordHash())) {
            throw new InvalidCredentialsException();
        }

        issueNewRefreshToken(user);
        userRepository.save(user);

        String accessToken = jwtService.generateAccessToken(user.getId(), user.getEmail(), user.getRole());
        return new AuthResponse(accessToken, currentRawRefreshToken);
    }

    public AuthResponse refresh(RefreshRequest request) {
        String incomingHash = hashToken(request.refreshToken());

        User user = userRepository.findByRefreshTokenHash(incomingHash)
                .orElseThrow(InvalidRefreshTokenException::new);

        if (user.getRefreshTokenExpiry() == null || Instant.now().isAfter(user.getRefreshTokenExpiry())) {
            throw new InvalidRefreshTokenException();
        }

        issueNewRefreshToken(user);
        userRepository.save(user);

        String accessToken = jwtService.generateAccessToken(user.getId(), user.getEmail(), user.getRole());
        return new AuthResponse(accessToken, currentRawRefreshToken);
    }

    private String currentRawRefreshToken;

    private void issueNewRefreshToken(User user) {
        currentRawRefreshToken = generateRawRefreshToken();
        user.setRefreshTokenHash(hashToken(currentRawRefreshToken));
        user.setRefreshTokenExpiry(Instant.now().plusMillis(refreshTokenExpirationMs));
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