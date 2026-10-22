export type * from "../../../packages/contracts";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, { ...init, cache: "no-store", credentials: "same-origin" });
  } catch {
    throw new ApiError(0, "CONNECTION_LOST", "Connection lost. Reload the current state before trying again.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, body?.error?.code ?? "UNAVAILABLE",
      body?.error?.message ?? "The service is unavailable. Please try again.");
  }
  return response.status === 204 ? undefined as T : response.json();
}

export function json(body: unknown, key?: string): RequestInit {
  return { method: "POST", headers: { "Content-Type": "application/json", ...(key ? { "Idempotency-Key": key } : {}) }, body: JSON.stringify(body) };
}

export function message(error: unknown): string {
  return error instanceof Error ? error.message : "The request could not be completed.";
}
