package com.ainvest.identity.domain.model;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;

import java.time.Instant;
import java.util.UUID;

@Getter
@Setter
@Entity
@Table(name ="users")

public class User {
    @Id
    @GeneratedValue(strategy= GenerationType.UUID)
    private UUID id;

    @Column (unique = true,nullable = false)
    private String email;

    @Column(nullable = false)
    private String passwordHash;

    @Column(nullable = false)
    private String role="USER";

    private String refreshTokenHash;

    private Instant refreshTokenExpiry;

    @Column(nullable = false, updatable = false)
    private Instant createdAt;
}
