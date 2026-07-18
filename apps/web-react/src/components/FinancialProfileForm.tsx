import type { ChangeEvent, FormEvent } from "react";
import type { FinancialProfileFormData } from "../types/finance";

interface FinancialProfileFormProps {
  form: FinancialProfileFormData;
  loading: boolean;
  onChange: (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

function FinancialProfileForm({
  form,
  loading,
  onChange,
  onSubmit,
}: FinancialProfileFormProps) {
  return (
    <form onSubmit={onSubmit}>
      <h2>Financial Profile</h2>

      <div>
        <label>User ID</label>
        <input
          type="text"
          name="userId"
          value={form.userId}
          onChange={onChange}
          placeholder="Example: demo-user-1"
          required
        />
      </div>

      <div>
        <label>Monthly Income</label>
        <input
          type="number"
          name="monthlyIncome"
          value={form.monthlyIncome}
          onChange={onChange}
          placeholder="Example: 50000"
          min="0"
        />
      </div>

      <div>
        <label>Monthly Expenses</label>
        <input
          type="number"
          name="monthlyExpenses"
          value={form.monthlyExpenses}
          onChange={onChange}
          placeholder="Example: 25000"
          min="0"
        />
      </div>

      <div>
        <label>Monthly Debt Payment</label>
        <input
          type="number"
          name="monthlyDebtPayment"
          value={form.monthlyDebtPayment}
          onChange={onChange}
          placeholder="Example: 5000"
          min="0"
        />
      </div>

      <div>
        <label>Total Debt</label>
        <input
          type="number"
          name="totalDebt"
          value={form.totalDebt}
          onChange={onChange}
          placeholder="Example: 100000"
          min="0"
        />
      </div>

      <div>
        <label>Cash Reserve</label>
        <input
          type="number"
          name="cashReserve"
          value={form.cashReserve}
          onChange={onChange}
          placeholder="Example: 30000"
          min="0"
        />
      </div>

      <div>
        <label>Investment Amount</label>
        <input
          type="number"
          name="investmentAmount"
          value={form.investmentAmount}
          onChange={onChange}
          placeholder="Example: 10000"
          min="0"
        />
      </div>

      <div>
        <label>Risk Preference</label>
        <select
          name="riskPreference"
          value={form.riskPreference}
          onChange={onChange}
        >
          <option value="LOW">Low</option>
          <option value="MEDIUM">Medium</option>
          <option value="HIGH">High</option>
        </select>
      </div>

      <button type="submit" disabled={loading}>
        {loading ? "Calculating..." : "Save & Calculate"}
      </button>
    </form>
  );
}

export default FinancialProfileForm;