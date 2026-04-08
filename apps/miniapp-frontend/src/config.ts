// -------------------------------------------------------------------------- //
//                                   CONFIG                                   //
// -------------------------------------------------------------------------- //

export const API = (import.meta as ImportMeta & { env: Record<string, string | undefined> }).env
  .VITE_API_BASE_URL || `${window.location.origin}/api`;
