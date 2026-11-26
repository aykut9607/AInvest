/// <reference types="vite/client" />

// variables read in src/config.ts; both are optional, config.ts has a default for each
interface ImportMetaEnv {
  readonly VITE_GATEWAY_URL?: string;
  readonly VITE_PORTFOLIO_SOURCE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
