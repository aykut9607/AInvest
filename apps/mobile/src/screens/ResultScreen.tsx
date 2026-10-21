import { useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import Card from "../components/Card";
import FactorBar from "../components/FactorBar";
import PrimaryButton from "../components/PrimaryButton";
import { explainScore } from "../api/aiApi";
import { colors, segmentColor, spacing } from "../theme";
import type { Explanation, IqResult, RiskProfile } from "../types";

interface Props {
  result: IqResult;
  onEditProfile: () => void;
}

// display order, label and maximum points of each factor (weights of the 6-factor model)
const FACTORS: { key: string; label: string; max: number }[] = [
  { key: "CashReserveMonths", label: "Cash reserve", max: 20 },
  { key: "DebtToIncomeRatio", label: "Debt to income", max: 20 },
  { key: "SavingsRate", label: "Savings rate", max: 20 },
  { key: "ExpenseRatio", label: "Expense ratio", max: 15 },
  { key: "RiskAlignment", label: "Risk alignment", max: 15 },
  { key: "Impatience", label: "Patience", max: 10 },
];

export default function ResultScreen({ result, onEditProfile }: Props) {
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [error, setError] = useState("");

  const accent = segmentColor[result.segment];
  const breakdown = result.breakdown;

  const handleExplain = async () => {
    setExplaining(true);
    setError("");
    try {
      setExplanation(await explainScore(result.score, result.segment));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not get an explanation.");
    } finally {
      setExplaining(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.scoreBlock}>
        <View style={[styles.scoreRing, { borderColor: accent }]}>
          <Text style={[styles.score, { color: accent }]}>{result.score}</Text>
          <Text style={styles.scoreMax}>/ 100</Text>
        </View>
        <View style={[styles.segmentBadge, { backgroundColor: accent }]}>
          <Text style={styles.segmentText}>{result.segment}</Text>
        </View>
        <Text style={styles.caption}>Financial IQ</Text>
      </View>

      {breakdown?.riskProfile ? <RiskProfileCard profile={breakdown.riskProfile} /> : null}

      {breakdown ? (
        <Card title="Score breakdown">
          {FACTORS.map((factor) => (
            <FactorBar
              key={factor.key}
              label={factor.label}
              points={breakdown.factors[factor.key] ?? 0}
              max={factor.max}
            />
          ))}
        </Card>
      ) : null}

      {breakdown && breakdown.warnings.length > 0 ? (
        <Card title="Warnings">
          {breakdown.warnings.map((warning) => (
            <View key={warning} style={styles.warningRow}>
              <View style={styles.warningDot} />
              <Text style={styles.warningText}>{warning}</Text>
            </View>
          ))}
        </Card>
      ) : null}

      <Card title="AI explanation">
        {explanation ? (
          <>
            <Text style={styles.explanation}>{explanation.explanation}</Text>
            <Text style={styles.disclaimer}>{explanation.disclaimer}</Text>
          </>
        ) : (
          <Text style={styles.muted}>Ask the AI service why your score looks like this.</Text>
        )}
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <PrimaryButton
          title={explanation ? "Explain again" : "Explain my score"}
          onPress={handleExplain}
          loading={explaining}
          variant="outline"
        />
      </Card>

      <PrimaryButton title="Edit profile" onPress={onEditProfile} />
    </ScrollView>
  );
}

function RiskProfileCard({ profile }: { profile: RiskProfile }) {
  const overstated = profile.direction === "OVERSTATED";
  const tone = overstated
    ? { bg: colors.dangerSoft, fg: colors.danger, title: "Risk mismatch" }
    : profile.inconsistent
      ? { bg: colors.warningSoft, fg: colors.warning, title: "More careful than needed" }
      : { bg: colors.successSoft, fg: colors.success, title: "Risk profile aligned" };

  return (
    <View style={[styles.riskCard, { backgroundColor: tone.bg, borderColor: tone.fg }]}>
      <Text style={[styles.riskTitle, { color: tone.fg }]}>{tone.title}</Text>
      <View style={styles.riskRow}>
        <View style={styles.riskCol}>
          <Text style={styles.riskLabel}>You say</Text>
          <Text style={styles.riskValue}>{profile.stated}</Text>
        </View>
        <Text style={[styles.riskVs, { color: tone.fg }]}>{overstated ? ">" : profile.inconsistent ? "<" : "="}</Text>
        <View style={styles.riskCol}>
          <Text style={styles.riskLabel}>Your numbers say</Text>
          <Text style={styles.riskValue}>{profile.behavioral}</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: spacing.lg, paddingBottom: spacing.xl * 2 },
  scoreBlock: { alignItems: "center", marginVertical: spacing.lg },
  scoreRing: {
    width: 160,
    height: 160,
    borderRadius: 80,
    borderWidth: 10,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.card,
  },
  score: { fontSize: 52, fontWeight: "800", fontVariant: ["tabular-nums"] },
  scoreMax: { color: colors.muted, marginTop: -4 },
  segmentBadge: { marginTop: spacing.md, paddingHorizontal: spacing.lg, paddingVertical: spacing.xs, borderRadius: 20 },
  segmentText: { color: "#FFFFFF", fontWeight: "700", letterSpacing: 1 },
  caption: { color: colors.muted, marginTop: spacing.sm },
  riskCard: { borderWidth: 1.5, borderRadius: 14, padding: spacing.lg, marginBottom: spacing.lg },
  riskTitle: { fontWeight: "700", fontSize: 16, marginBottom: spacing.md },
  riskRow: { flexDirection: "row", alignItems: "center" },
  riskCol: { flex: 1, alignItems: "center" },
  riskLabel: { color: colors.muted, fontSize: 12 },
  riskValue: { color: colors.text, fontSize: 20, fontWeight: "700", marginTop: 2 },
  riskVs: { fontSize: 24, fontWeight: "800", paddingHorizontal: spacing.md },
  warningRow: { flexDirection: "row", alignItems: "center", marginBottom: spacing.sm },
  warningDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.warning, marginRight: spacing.sm },
  warningText: { color: colors.text, flex: 1 },
  explanation: { color: colors.text, fontSize: 15, lineHeight: 22 },
  disclaimer: { color: colors.muted, fontSize: 12, marginTop: spacing.sm, fontStyle: "italic" },
  muted: { color: colors.muted },
  error: { color: colors.danger, marginTop: spacing.sm },
});
