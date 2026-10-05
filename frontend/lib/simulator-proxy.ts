import "server-only";

import { NextResponse } from "next/server";

import { ApiError } from "@/lib/api/client";

/** The API's status and message for the simulator's route handlers (503 if unreachable). */
export function proxyError(error: unknown) {
  const status = error instanceof ApiError && error.status ? error.status : 503;
  const detail = error instanceof ApiError ? error.message : "the simulator is unavailable";
  return NextResponse.json({ detail }, { status });
}
