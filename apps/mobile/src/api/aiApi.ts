import type { Explanation, Segment } from "../types";
import { authorizedRequest } from "./authorizedRequest";
import { ApiError, messageFrom } from "./http";

export async function explainScore(score: number, segment: Segment): Promise<Explanation> {
  const { status, body } = await authorizedRequest<Explanation>("/ai/explain-financial-iq", {
    method: "POST",
    body: { score, segment },
  });

  if (status !== 200 || !body?.explanation) {
    throw new ApiError(messageFrom(body, "Could not get an explanation."), status);
  }
  return body;
}
