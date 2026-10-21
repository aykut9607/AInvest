import { ActivityIndicator, Pressable, StyleSheet, Text } from "react-native";
import { colors, spacing } from "../theme";

interface Props {
  title: string;
  onPress: () => void;
  loading?: boolean;
  variant?: "solid" | "outline";
}

export default function PrimaryButton({ title, onPress, loading = false, variant = "solid" }: Props) {
  const outline = variant === "outline";

  return (
    <Pressable
      onPress={onPress}
      disabled={loading}
      style={({ pressed }) => [
        styles.button,
        outline ? styles.outline : styles.solid,
        (pressed || loading) && styles.dimmed,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={outline ? colors.primary : colors.primaryText} />
      ) : (
        <Text style={[styles.title, outline && styles.outlineTitle]}>{title}</Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    borderRadius: 10,
    paddingVertical: spacing.md + 2,
    alignItems: "center",
    marginTop: spacing.md,
  },
  solid: { backgroundColor: colors.primary },
  outline: { borderWidth: 1.5, borderColor: colors.primary, backgroundColor: "transparent" },
  dimmed: { opacity: 0.6 },
  title: { color: colors.primaryText, fontSize: 16, fontWeight: "600" },
  outlineTitle: { color: colors.primary },
});
