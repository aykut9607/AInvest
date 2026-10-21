import { useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, View } from "react-native";
import Field from "../components/Field";
import PrimaryButton from "../components/PrimaryButton";
import { login, register } from "../api/identityApi";
import { colors, spacing } from "../theme";
import type { AuthSession } from "../types";

interface Props {
  onAuthenticated: (session: AuthSession) => void;
}

export default function AuthScreen({ onAuthenticated }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isLogin = mode === "login";

  const handleSubmit = async () => {
    if (!email.trim() || !password) {
      setError("Email and password are required.");
      return;
    }

    setLoading(true);
    setError("");
    try {
      const session = isLogin
        ? await login(email.trim(), password)
        : await register(email.trim(), password);
      onAuthenticated(session);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <View style={styles.brand}>
          <Text style={styles.logo}>AInvest</Text>
          <Text style={styles.tagline}>Know your Financial IQ</Text>
        </View>

        <Text style={styles.heading}>{isLogin ? "Sign in" : "Create account"}</Text>

        <Field
          label="Email"
          value={email}
          onChangeText={setEmail}
          placeholder="demo@ainvest.dev"
          keyboardType="email-address"
        />
        <Field label="Password" value={password} onChangeText={setPassword} secureTextEntry />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <PrimaryButton title={isLogin ? "Sign in" : "Register"} onPress={handleSubmit} loading={loading} />
        <PrimaryButton
          title={isLogin ? "No account? Register" : "Have an account? Sign in"}
          variant="outline"
          onPress={() => {
            setMode(isLogin ? "register" : "login");
            setError("");
          }}
        />

        <Text style={styles.footnote}>Identity Service · Spring Boot · JWT</Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  container: { flexGrow: 1, justifyContent: "center", padding: spacing.xl },
  brand: { alignItems: "center", marginBottom: spacing.xl * 1.5 },
  logo: { fontSize: 36, fontWeight: "800", color: colors.primary },
  tagline: { fontSize: 15, color: colors.muted, marginTop: spacing.xs },
  heading: { fontSize: 22, fontWeight: "700", color: colors.text, marginBottom: spacing.lg },
  error: { color: colors.danger, marginBottom: spacing.sm },
  footnote: { textAlign: "center", color: colors.muted, fontSize: 12, marginTop: spacing.xl },
});
