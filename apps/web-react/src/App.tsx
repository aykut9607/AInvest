import { useState, type ChangeEvent, type FormEvent } from "react";
import "./App.css";

import FinancialProfileForm from "./components/FinancialProfileForm";
import ScoreCard from "./components/ScoreCard";

import { saveAndCalculateFinancialScore } from "./api/financeApi";
import { explainFinancialScore } from "./api/explainApi";

import type {
  FinancialProfileFormData,
  FinancialScoreResult,
} from "./types/finance";

function App() {
  const [form, setForm] = useState<FinancialProfileFormData>({
    userId: "",
    monthlyIncome: "",
    monthlyExpenses: "",
    monthlyDebtPayment: "",
    totalDebt: "",
    cashReserve: "",
    investmentAmount: "",
    riskPreference: "MEDIUM",
  });

  const [result, setResult] = useState<FinancialScoreResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [explanation, setExplanation] = useState<string | null>(null);
  const [explanationDisclaimer, setExplanationDisclaimer] = useState<string | null>(null);
  const [explainLoading, setExplainLoading] = useState(false);
  const [explainError, setExplainError] = useState("");

  const handleChange = (
    event: ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    const { name, value } = event.target;

    setForm((previousForm) => ({
      ...previousForm,
      [name]: value,
    } as FinancialProfileFormData));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setLoading(true);
    setError("");
    setExplanation(null);
    setExplanationDisclaimer(null);
    setExplainError("");

    try {
      const calculatedResult = await saveAndCalculateFinancialScore(form.userId, form);
      setResult(calculatedResult);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong while calculating the financial score."
      );
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const handleExplain = async () => {
    if (!result) return;

    setExplainLoading(true);
    setExplainError("");

    try {
      const explainResult = await explainFinancialScore(result.score, result.segment);
      setExplanation(explainResult.explanation);
      setExplanationDisclaimer(explainResult.disclaimer);
    } catch {
      setExplainError("Something went wrong while explaining the financial score.");
    } finally {
      setExplainLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>AInvest Mock</h1>
        <p>Financial Readiness Score Prototype</p>
      </header>

      <FinancialProfileForm
        form={form}
        loading={loading}
        onChange={handleChange}
        onSubmit={handleSubmit}
      />

      {error && <p className="error-message">{error}</p>}

      <ScoreCard
        result={result}
        explanation={explanation}
        explanationDisclaimer={explanationDisclaimer}
        explainLoading={explainLoading}
        explainError={explainError}
        onExplain={handleExplain}
      />
    </div>
  );
}

export default App;