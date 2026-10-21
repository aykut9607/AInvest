import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, spacing } from "../theme";

interface Option<T> {
  value: T;
  label: string;
}

interface Props<T> {
  label: string;
  options: Option<T>[];
  value: T;
  onChange: (value: T) => void;
  hint?: string;
}

// segmented control: every option is visible at once, no native picker needed
export default function OptionGroup<T extends string | number>({ label, options, value, onChange, hint }: Props<T>) {
  return (
    <View style={styles.wrapper}>
      <Text style={styles.label}>{label}</Text>
      <View style={styles.row}>
        {options.map((option) => {
          const selected = option.value === value;
          return (
            <Pressable
              key={String(option.value)}
              onPress={() => onChange(option.value)}
              style={[styles.option, selected && styles.selected]}
            >
              <Text style={[styles.optionText, selected && styles.selectedText]}>{option.label}</Text>
            </Pressable>
          );
        })}
      </View>
      {hint ? <Text style={styles.hint}>{hint}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { marginBottom: spacing.md },
  label: { fontSize: 13, color: colors.muted, marginBottom: spacing.xs, fontWeight: "500" },
  row: { flexDirection: "row", gap: spacing.sm },
  option: {
    flex: 1,
    paddingVertical: spacing.sm + 2,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.card,
    alignItems: "center",
  },
  selected: { backgroundColor: colors.primary, borderColor: colors.primary },
  optionText: { color: colors.text, fontWeight: "500" },
  selectedText: { color: colors.primaryText },
  hint: { fontSize: 12, color: colors.muted, marginTop: spacing.xs },
});
