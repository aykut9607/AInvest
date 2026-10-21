import { StyleSheet, Text, View } from "react-native";
import { colors, spacing } from "../theme";

interface Props {
  label: string;
  points: number;
  max: number;
}

export default function FactorBar({ label, points, max }: Props) {
  const ratio = max > 0 ? Math.min(points / max, 1) : 0;
  // same thresholds feel as the segments: strong / partial / weak
  const fill = ratio >= 0.7 ? colors.success : ratio >= 0.4 ? colors.warning : colors.danger;

  return (
    <View style={styles.wrapper}>
      <View style={styles.header}>
        <Text style={styles.label}>{label}</Text>
        <Text style={styles.points}>
          {points} / {max}
        </Text>
      </View>
      <View style={styles.track}>
        <View style={[styles.fill, { width: `${ratio * 100}%`, backgroundColor: fill }]} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { marginBottom: spacing.md },
  header: { flexDirection: "row", justifyContent: "space-between", marginBottom: spacing.xs },
  label: { color: colors.text, fontSize: 14 },
  points: { color: colors.muted, fontSize: 14, fontVariant: ["tabular-nums"] },
  track: { height: 8, borderRadius: 4, backgroundColor: colors.track, overflow: "hidden" },
  fill: { height: "100%", borderRadius: 4 },
});
