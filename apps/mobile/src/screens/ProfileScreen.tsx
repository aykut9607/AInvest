import { useEffect, useState } from "react";
import { ActivityIndicator, KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, View } from "react-native";
import Card from "../components/Card";
import Field from "../components/Field";
import OptionGroup from "../components/OptionGroup";
import PrimaryButton from "../components/PrimaryButton";
import { calculateIq, getProfile, saveProfile } from "../api/financeApi";
import { colors, spacing } from "../theme";
import type { AuthSession, IqResult, ProfileForm, RiskLevel } from "../types";

interface Props {
  session: AuthSession;
  onCalculated: (result: IqResult) => void;
  onLogout: () => void;
}

const emptyForm: ProfileForm = {
  monthlyIncome: "",
  monthlyExpenses: "",
  monthlyDebtPayment: "",
  totalDebt: "",
  cashReserve: "",
  investmentAmount: "",
  riskPreference: "MEDIUM",
  impatienceLevel: 3,
};

const impatienceHints: Record<number, string> = {
  1: "Years, I'm in no hurry",
  2: "A year or two",
  3: "Several months",
  4: "A few weeks",
  5: "I want results right away",
};

export default function ProfileScreen({ session, onCalculated, onLogout }: Props) {
  const [form, setForm] = useState<ProfileForm>(emptyForm);
  const [loadingProfile, setLoadingProfile] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // returning users get their saved profile back, new users start with an empty form
  useEffect(() => {
    let active = true;
    getProfile(session.userId)
      .then((profile) => {
        if (!active || !profile) return;
        setForm({
          monthlyIncome: String(profile.monthlyIncome),
          monthlyExpenses: String(profile.monthlyExpenses),
          monthlyDebtPayment: String(profile.monthlyDebtPayment),
          totalDebt: String(profile.totalDebt),
          cashReserve: String(profile.cashReserve),
          investmentAmount: String(profile.investmentAmount),
          riskPreference: profile.riskPreference,
          impatienceLevel: profile.impatienceLevel,
        });
      })
      .catch((err) => active && setError(err instanceof Error ? err.message : "Could not load the profile."))
      .finally(() => active && setLoadingProfile(false));
    return () => {
      active = false;
    };
  }, [session.userId]);

  const update = (key: keyof ProfileForm) => (value: string) => setForm((prev) => ({ ...prev, [key]: value }));

  const handleSubmit = async () => {
    if (!(Number(form.monthlyIncome.replace(",", ".")) > 0)) {
      setError("Monthly income must be greater than zero.");
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      await saveProfile(session.userId, form);
      const result = await calculateIq(session.userId);
      onCalculated(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loadingProfile) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  return (
    <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        {/* Sign out lives at the bottom: the top-right corner is covered by Expo Go's floating tools button */}
        <View style={styles.header}>
          <Text style={styles.heading}>Financial profile</Text>
          <Text style={styles.email}>{session.email}</Text>
        </View>

        <Card title="Monthly">
          <Field label="Income" value={form.monthlyIncome} onChangeText={update("monthlyIncome")} keyboardType="numeric" placeholder="e.g. 50000" />
          <Field label="Expenses" value={form.monthlyExpenses} onChangeText={update("monthlyExpenses")} keyboardType="numeric" placeholder="e.g. 25000" />
          <Field label="Debt payment" value={form.monthlyDebtPayment} onChangeText={update("monthlyDebtPayment")} keyboardType="numeric" placeholder="e.g. 5000" />
        </Card>

        <Card title="Balances">
          <Field label="Total debt" value={form.totalDebt} onChangeText={update("totalDebt")} keyboardType="numeric" placeholder="e.g. 100000" />
          <Field label="Cash reserve" value={form.cashReserve} onChangeText={update("cashReserve")} keyboardType="numeric" placeholder="e.g. 30000" />
          <Field label="Investments" value={form.investmentAmount} onChangeText={update("investmentAmount")} keyboardType="numeric" placeholder="e.g. 10000" />
        </Card>

        <Card title="About you">
          <OptionGroup<RiskLevel>
            label="Risk preference"
            value={form.riskPreference}
            onChange={(riskPreference) => setForm((prev) => ({ ...prev, riskPreference }))}
            options={[
              { value: "LOW", label: "Low" },
              { value: "MEDIUM", label: "Medium" },
              { value: "HIGH", label: "High" },
            ]}
          />
          <OptionGroup<number>
            label="How long can you wait to see a return?"
            value={form.impatienceLevel}
            onChange={(impatienceLevel) => setForm((prev) => ({ ...prev, impatienceLevel }))}
            options={[1, 2, 3, 4, 5].map((level) => ({ value: level, label: String(level) }))}
            hint={impatienceHints[form.impatienceLevel]}
          />
        </Card>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <PrimaryButton title="Save & calculate Financial IQ" onPress={handleSubmit} loading={submitting} />
        <PrimaryButton title="Sign out" variant="outline" onPress={onLogout} />
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  container: { padding: spacing.lg, paddingBottom: spacing.xl * 2 },
  header: { marginBottom: spacing.lg },
  heading: { fontSize: 24, fontWeight: "700", color: colors.text },
  email: { color: colors.muted, marginTop: 2 },
  error: { color: colors.danger, marginBottom: spacing.sm },
});
