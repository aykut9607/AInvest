import type { Explanation, FactorBreakdown, Segment } from "../types";
import { authorizedRequest } from "./authorizedRequest";
import { ApiError, messageFrom } from "./http";

// factorBreakdown is an optional field: the AI service uses it to explain the factors, warnings and the
// applied rule; a service that doesn't know the field ignores it
export async function explainScore(
  score: number,
  segment: Segment,
  factorBreakdown: FactorBreakdown | null
): Promise<Explanation> {
  const { status, body } = await authorizedRequest<Explanation>("/ai/explain-financial-iq", {
    method: "POST",
    body: factorBreakdown ? { score, segment, factorBreakdown } : { score, segment },
  });

  if (status !== 200 || !body?.explanation) {
    throw new ApiError(messageFrom(body, "Could not get an explanation."), status);
  }
  return body;
}
