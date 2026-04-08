// -------------------------------------------------------------------------- //
//                                   CONFIG                                   //
// -------------------------------------------------------------------------- //

export const ADMIN_EMAIL_KEY = "car-inspection-admin-email";
export const ADMIN_TOKEN_KEY = "car-inspection-admin-token";
export const API = (import.meta as ImportMeta & { env: Record<string, string | undefined> }).env
  .VITE_API_BASE_URL || `${window.location.origin}/api`;
