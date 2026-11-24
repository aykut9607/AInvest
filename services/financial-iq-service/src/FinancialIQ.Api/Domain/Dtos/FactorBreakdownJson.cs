using System.Text.Json;

namespace FinancialIQ.Api.Domain.Dtos;

// The breakdown is stored as JSON text (nvarchar(max)), but since contract v2 the API returns it as a JSON object,
// so clients no longer have to JSON.parse a string inside the response.
public static class FactorBreakdownJson
{
    // empty or unreadable text becomes {} instead of failing the whole response
    public static JsonElement ToElement(string? json)
    {
        if (string.IsNullOrWhiteSpace(json)) return EmptyObject();

        try
        {
            using var document = JsonDocument.Parse(json);
            // Clone: the element must outlive the document, which is disposed here
            return document.RootElement.Clone();
        }
        catch (JsonException)
        {
            return EmptyObject();
        }
    }

    private static JsonElement EmptyObject()
    {
        using var document = JsonDocument.Parse("{}");
        return document.RootElement.Clone();
    }
}
