import type { Segment } from "./types";

export const colors = {
  background: "#F4F6FA",
  card: "#FFFFFF",
  primary: "#1E3A5F",
  primaryText: "#FFFFFF",
  text: "#1B2430",
  muted: "#6B7685",
  placeholder: "#A9B2BF",
  border: "#DDE2EA",
  track: "#E8ECF2",
  danger: "#C0392B",
  dangerSoft: "#FDECEA",
  warning: "#B9770E",
  warningSoft: "#FEF5E7",
  success: "#1E8449",
  successSoft: "#E9F7EF",
};

export const segmentColor: Record<Segment, string> = {
  HIGH: colors.success,
  MEDIUM: colors.warning,
  LOW: colors.danger,
};

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24 };
