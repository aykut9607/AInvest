import { useEffect, useState } from "react";
import { BackHandler, StyleSheet } from "react-native";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import AuthScreen from "./src/screens/AuthScreen";
import ProfileScreen from "./src/screens/ProfileScreen";
import ResultScreen from "./src/screens/ResultScreen";
import { onSessionExpired, setSession as storeSession } from "./src/api/session";
import { colors } from "./src/theme";
import type { AuthSession, IqResult } from "./src/types";

// three screens only, so a small state machine replaces a navigation library
export default function App() {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [result, setResult] = useState<IqResult | null>(null);
  // shown on the sign-in screen after the session ran out (refresh token rejected)
  const [notice, setNotice] = useState("");

  // the API layer refreshes the access token by itself; only when that fails does the user sign in again
  useEffect(() => {
    onSessionExpired(() => {
      setResult(null);
      setSession(null);
      setNotice("Your session has expired. Please sign in again.");
    });
    return () => onSessionExpired(null);
  }, []);

  const signIn = (newSession: AuthSession) => {
    storeSession(newSession);
    setNotice("");
    setSession(newSession);
  };

  // Android back button: result -> profile, otherwise default behaviour (leave the app)
  useEffect(() => {
    const subscription = BackHandler.addEventListener("hardwareBackPress", () => {
      if (result) {
        setResult(null);
        return true;
      }
      return false;
    });
    return () => subscription.remove();
  }, [result]);

  const logout = () => {
    storeSession(null);
    setResult(null);
    setSession(null);
  };

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.root}>
        <StatusBar style="dark" />
        {!session ? (
          <AuthScreen onAuthenticated={signIn} notice={notice} />
        ) : result ? (
          <ResultScreen result={result} onEditProfile={() => setResult(null)} />
        ) : (
          <ProfileScreen session={session} onCalculated={setResult} onLogout={logout} />
        )}
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
});
