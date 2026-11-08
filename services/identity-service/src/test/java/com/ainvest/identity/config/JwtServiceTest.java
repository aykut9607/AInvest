package com.ainvest.identity.config;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.nio.charset.StandardCharsets;
import java.util.Date;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

// the token is what the gateway validates, so its issuer, audience, subject and signature are checked here (no DB)
class JwtServiceTest {

    private static final String SECRET = "test-only-secret-key-that-is-long-enough-for-hs512-signing-1234567890";

    private JwtService jwtService;

    @BeforeEach
    void setUp() {
        jwtService = new JwtService();
        ReflectionTestUtils.setField(jwtService, "secret", SECRET);
        ReflectionTestUtils.setField(jwtService, "accessTokenExpirationMs", 900_000L);
    }

    @Test
    void accessToken_carriesIssuerAudienceAndUserId() {
        UUID userId = UUID.randomUUID();

        String token = jwtService.generateAccessToken(userId, "user@ainvest.dev", "USER");

        Claims claims = Jwts.parser()
                .verifyWith(Keys.hmacShaKeyFor(SECRET.getBytes(StandardCharsets.UTF_8)))
                .build()
                .parseSignedClaims(token)
                .getPayload();
        assertEquals(JwtService.ISSUER, claims.getIssuer());
        assertTrue(claims.getAudience().contains(JwtService.AUDIENCE));
        assertEquals(userId.toString(), claims.getSubject());
        assertEquals(userId, jwtService.extractUserId(token));
    }

    @Test
    void accessToken_isSignedWithHs512() {
        String token = jwtService.generateAccessToken(UUID.randomUUID(), "user@ainvest.dev", "USER");

        String alg = Jwts.parser()
                .verifyWith(Keys.hmacShaKeyFor(SECRET.getBytes(StandardCharsets.UTF_8)))
                .build()
                .parseSignedClaims(token)
                .getHeader()
                .getAlgorithm();
        // the gateway only accepts HS512, so the algorithm jjwt picks for this key size must stay HS512
        assertEquals("HS512", alg);
    }

    @Test
    void tokenSignedWithAnotherKey_isNotValid() {
        String foreignToken = Jwts.builder()
                .issuer(JwtService.ISSUER)
                .audience().add(JwtService.AUDIENCE).and()
                .subject(UUID.randomUUID().toString())
                .expiration(new Date(System.currentTimeMillis() + 60_000))
                .signWith(Keys.hmacShaKeyFor("another-secret-key-that-is-also-long-enough-for-hs512-0987654321!!".getBytes(StandardCharsets.UTF_8)))
                .compact();

        assertFalse(jwtService.isTokenValid(foreignToken));
    }

    @Test
    void tokenForAnotherAudience_isNotValid() {
        String token = Jwts.builder()
                .issuer(JwtService.ISSUER)
                .audience().add("some-other-api").and()
                .subject(UUID.randomUUID().toString())
                .expiration(new Date(System.currentTimeMillis() + 60_000))
                .signWith(Keys.hmacShaKeyFor(SECRET.getBytes(StandardCharsets.UTF_8)))
                .compact();

        assertFalse(jwtService.isTokenValid(token));
    }
}
