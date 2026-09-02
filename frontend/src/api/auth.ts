import { ENDPOINTS } from "./endpoints";

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

export async function loginAPI(payload: DevLoginPayload): Promise<TokenPair> {
  const response = await fetch(ENDPOINTS.AUTH.LOGIN, {
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

/**
 * Exchange the performance portal's own JWT (arriving as `?token=...`) for a
 * Monitra session. The portal token is only ever sent to our backend, which
 * verifies it with the portal before issuing anything.
 */
export async function ssoLoginAPI(token: string): Promise<TokenPair> {
  const response = await fetch(ENDPOINTS.AUTH.SSO_TOKEN, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ token }),
  });

  if (!response.ok) {
    let errorDetail = "This sign-in link is no longer valid. Please sign in below.";
    try {
      const errorData = await response.json();
      if (errorData.detail && typeof errorData.detail === "object" && errorData.detail.message) {
        errorDetail = errorData.detail.message;
      } else if (errorData.detail) {
        errorDetail = errorData.detail;
      }
    } catch {
      // Ignore - the default message already explains what the user should do.
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
  const response = await fetch(ENDPOINTS.AUTH.ME, {
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
