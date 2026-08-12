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
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      username: payload.email,
      password: payload.password
    }),
  });

  if (!response.ok) {
    let errorDetail = "Failed to login";
    try {
      const errorData = await response.json();
      if (errorData.detail && typeof errorData.detail === "object" && errorData.detail.message) {
        errorDetail = errorData.detail.message;
      } else {
        errorDetail = errorData.detail || errorDetail;
      }
    } catch {
      // Ignore
    }
    throw new Error(errorDetail);
  }

  return response.json();
}
