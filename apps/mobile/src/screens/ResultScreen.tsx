import { useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import Card from "../components/Card";
import FactorBar from "../components/FactorBar";
import PrimaryButton from "../components/PrimaryButton";
import { explainScore } from "../api/aiApi";
import { colors, segmentColor, spacing } from "../theme";
import type { AppliedRule, Explanation, IqResult } from "../types";

interface Props {
  result: IqResult;
  onEditProfile: () => void;
}

// display order, label and maximum points of each factor (weights of the 5-factor model, scoring v2)
const FACTORS: { key: string; label: string; max: number }[] = [
  { key: "CashReserveMonths", label: "Cash reserve", max: 25 },
  { key: "DebtToIncomeRatio", label: "Debt to income", max: 25 },
  { key: "SavingsRate", label: "Savings rate", max: 25 },
  { key: "ExpenseRatio", label: "Expense ratio", max: 15 },
  { key: "Impatience", label: "Patience", max: 10 },
];

// thresholds live in the Financial IQ service (ScoringRules.cs); these texts only explain them
const RULE_TEXT: Record<AppliedRule, string> = {
  VERY_HIGH_INCOME:
    "Your monthly income is 1,000,000 or more and your debt (minus cash and investments) is at most one year of income. At this level a cash reserve builds up quickly, so the score is set to 100.",
  VERY_HIGH_WEALTH:
    "Your cash and investments minus your debt are 10,000,000 or more. This covers your expenses for a very long time, so the score is set to 100.",
  EXTREME_DEBT:
    "Your debt minus your cash and investments is 100,000,000 or more, which your income cannot carry. The score is set to 0.",
};

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
      setExplanation(await explainScore(result.score, result.segment, result.breakdown));
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

      {breakdown?.appliedRule ? (
        <Card title="How this score was set">
          <Text style={styles.ruleText}>{RULE_TEXT[breakdown.appliedRule]}</Text>
        </Card>
      ) : null}

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
  warningRow: { flexDirection: "row", alignItems: "center", marginBottom: spacing.sm },
  warningDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.warning, marginRight: spacing.sm },
  warningText: { color: colors.text, flex: 1 },
  ruleText: { color: colors.text, lineHeight: 20 },
  explanation: { color: colors.text, fontSize: 15, lineHeight: 22 },
  disclaimer: { color: colors.muted, fontSize: 12, marginTop: spacing.sm, fontStyle: "italic" },
  muted: { color: colors.muted },
  error: { color: colors.danger, marginTop: spacing.sm },
});
