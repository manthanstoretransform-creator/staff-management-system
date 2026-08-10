export interface DevLoginPayload {
  email: string;
  password: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function loginAPI(payload: DevLoginPayload): Promise<TokenPair> {
  const response = await fetch(`${API_BASE_URL}/auth/dev-login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorDetail = "Failed to login";
    try {
      const errorData = await response.json();
      errorDetail = errorData.detail || errorDetail;
    } catch {
      // Ignore
    }
    throw new Error(errorDetail);
  }

  return response.json();
}
