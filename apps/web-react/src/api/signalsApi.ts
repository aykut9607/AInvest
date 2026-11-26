import { SAMPLE_SIGNAL_PLANS } from "../mocks/signalPlans";
import type { SignalAsset, SignalPlan } from "../types/signals";

// 4.4 (AInvest önerisi): mock only. The Portfolio Service's 4.4 module has no API yet; when it gets one
// (planned: GET /api/portfolio/market/** through the gateway, same view for every user), replace the bodies
// below and keep the signatures. The returned plans are sample data (isSample: true).

export async function getSignalPlans(): Promise<SignalPlan[]> {
  return structuredClone(SAMPLE_SIGNAL_PLANS);
}

export async function getSignalPlan(asset: SignalAsset): Promise<SignalPlan | null> {
  const plan = SAMPLE_SIGNAL_PLANS.find((p) => p.asset === asset);
  return plan ? structuredClone(plan) : null;
}
