import { useState, type ChangeEvent, type FormEvent } from "react";
import "./App.css";

import FinancialProfileForm from "./components/FinancialProfileForm";
import ScoreCard from "./components/ScoreCard";

import { saveAndCalculateFinancialScore } from "./api/financeApi";

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

      <ScoreCard result={result} />
    </div>
  );
}

export default App;