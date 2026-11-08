using System.Net.Http.Headers;
using System.Text;
using Microsoft.IdentityModel.JsonWebTokens;
using Microsoft.IdentityModel.Tokens;

namespace EdgeGateway.Tests;

// builds tokens the same way Identity does (HS512, iss/aud/sub), plus broken variants for the negative tests
public static class TestTokens
{
    public const string Secret = "test-only-secret-key-that-is-long-enough-for-hs512-signing-1234567890";
    public const string Issuer = "ainvest-identity";
    public const string Audience = "ainvest-api";

    public static string Create(
        string userId,
        string secret = Secret,
        string issuer = Issuer,
        string audience = Audience,
        DateTime? expires = null)
    {
        var expiresAt = expires ?? DateTime.UtcNow.AddMinutes(15);
        return new JsonWebTokenHandler().CreateToken(new SecurityTokenDescriptor
        {
            Issuer = issuer,
            Audience = audience,
            Claims = new Dictionary<string, object> { ["sub"] = userId },
            IssuedAt = expiresAt.AddMinutes(-15),
            NotBefore = expiresAt.AddMinutes(-15),
            Expires = expiresAt,
            SigningCredentials = new SigningCredentials(
                new SymmetricSecurityKey(Encoding.UTF8.GetBytes(secret)), SecurityAlgorithms.HmacSha512)
        });
    }

    // header {"alg":"none"} and no signature: an old trick that some JWT libraries used to accept
    public static string Unsigned(string userId)
    {
        static string Base64Url(string json) =>
            Convert.ToBase64String(Encoding.UTF8.GetBytes(json)).TrimEnd('=').Replace('+', '-').Replace('/', '_');

        var exp = DateTimeOffset.UtcNow.AddMinutes(15).ToUnixTimeSeconds();
        return $"{Base64Url("{\"alg\":\"none\",\"typ\":\"JWT\"}")}." +
               $"{Base64Url($"{{\"sub\":\"{userId}\",\"iss\":\"{Issuer}\",\"aud\":\"{Audience}\",\"exp\":{exp}}}")}.";
    }

    public static HttpRequestMessage Get(string path, string? token = null)
    {
        var request = new HttpRequestMessage(HttpMethod.Get, path);
        if (token is not null)
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        return request;
    }
}
