using System.Buffers.Binary;

namespace FinancialIQ.Api.Domain.Dtos;

// the API shows the 8-byte rowversion as a plain number: easier to store and compare in JSON than a byte array.
// Same bytes, same order as T-SQL's CONVERT(bigint, row_version) (big-endian), so the C# read path and the
// usp_GetLatestIqResult read path return the same value for the same row.
// The number is a database-wide counter, not "how many times this row changed": it only ever grows, and a new
// value means the row was written again. Clients must compare it for equality, not do arithmetic on it.
public static class ResultVersion
{
    public static long FromRowVersion(byte[]? rowVersion) =>
        rowVersion is { Length: 8 } ? BinaryPrimitives.ReadInt64BigEndian(rowVersion) : 0;
}
