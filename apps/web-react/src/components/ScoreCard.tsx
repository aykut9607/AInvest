import type { FinancialScoreResult } from "../types/finance";

interface ScoreCardProps {
  result: FinancialScoreResult | null;
  explanation: string | null;
  explanationDisclaimer: string | null;
  explainLoading: boolean;
  explainError: string;
  onExplain: () => void;
}

function ScoreCard({
  result,
  explanation,
  explanationDisclaimer,
  explainLoading,
  explainError,
  onExplain,
}: ScoreCardProps) {
  if (result === null) {
    return null;
  }

  return (
    <div>
      <h2>Financial Score Result</h2>

      <p>
        <strong>Score:</strong> {result.score}
      </p>

      <p>
        <strong>Segment:</strong> {result.segment}
      </p>

      <button type="button" onClick={onExplain} disabled={explainLoading}>
        {explainLoading ? "Explaining..." : "Explain My Result"}
      </button>

      {explainError && <p className="error-message">{explainError}</p>}

      {explanation && (
        <div>
          <p>{explanation}</p>
          {explanationDisclaimer && <p><em>{explanationDisclaimer}</em></p>}
        </div>
      )}
    </div>
  );
}

export default ScoreCard;