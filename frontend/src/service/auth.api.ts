import { loginApiV1AuthLoginPost, meApiV1AuthMeGet } from '../client/sdk.gen';

const TOKEN_STORAGE_KEY = 'ise547.jwt.token';

export type LoginPayload = {
  username: string;
  password: string;
};

export type CurrentUser = {
  id: number;
  username: string;
  email: string;
};

export function getAccessToken(): string | undefined {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  return token ?? undefined;
}

export function setAccessToken(token: string): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function clearAccessToken(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

export async function login(payload: LoginPayload): Promise<void> {
  const result = await loginApiV1AuthLoginPost({
    body: payload,
  });
  const accessToken = result.data?.access_token;
  if (!accessToken) {
    throw new Error('login failed, no access token');
  }
  setAccessToken(accessToken);
}

export async function fetchCurrentUser(): Promise<CurrentUser | null> {
  const result = await meApiV1AuthMeGet();
  if (result.error || !result.data) {
    return null;
  }
  return result.data;
}
