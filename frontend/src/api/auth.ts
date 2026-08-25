export interface DevLoginPayload {
  email: string;
  password: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: UserRead;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE || import.meta.env.VITE_API_URL || "/api/v1";

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

export interface UserRead {
  id: number;
  organization_id: number;
  username: string;
  email: string;
  name: string;
  role_name: string;
  permissions: Record<string, boolean>;
  is_active: boolean;
}

export async function getMeAPI(token: string): Promise<UserRead> {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    method: "GET",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error("Unauthorized");
    }
    throw new Error("Failed to fetch user profile");
  }

  return response.json();
}
