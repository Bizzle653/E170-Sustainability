import { verifyAuth } from "@supabase/server/core";

export const runtime = "nodejs";

export async function GET(request: Request) {
  const { data: auth, error } = await verifyAuth(request, { auth: "user" });

  if (error) {
    return Response.json(
      { authenticated: false, message: error.message },
      { status: error.status },
    );
  }

  return Response.json({
    authenticated: true,
    user: {
      id: auth.userClaims?.id ?? null,
      email: auth.userClaims?.email ?? null,
      role: auth.userClaims?.role ?? null,
    },
  });
}
