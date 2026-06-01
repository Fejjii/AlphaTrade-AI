"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { EmailVerificationNotice } from "@/components/account/EmailVerificationNotice";
import { PaperModeBanner } from "@/components/PaperModeBanner";
import { ErrorState, SuccessState } from "@/components/states";
import { useAuth } from "@/contexts/AuthContext";
import { api, ApiError } from "@/lib/api";

function VerifyEmailContent() {
  const params = useSearchParams();
  const token = params.get("token");
  const { user, loading, refreshProfile } = useAuth();
  const [status, setStatus] = useState<"idle" | "confirming" | "success" | "error">(
    token ? "confirming" : "idle",
  );
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    void (async () => {
      try {
        const response = await api.auth.confirmVerifyEmail(token);
        setMessage(response.message);
        setStatus("success");
        await refreshProfile();
      } catch (err) {
        setMessage(err instanceof ApiError ? err.message : "Verification failed.");
        setStatus("error");
      }
    })();
  }, [token, refreshProfile]);

  if (loading) {
    return <p className="text-sm text-zinc-400">Loading…</p>;
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 px-4 py-10">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-50">Email verification</h1>
        <p className="text-sm text-zinc-400">Confirm your address to unlock staging and production policies.</p>
      </div>
      <PaperModeBanner />
      {status === "confirming" ? <p className="text-sm text-zinc-400">Confirming your link…</p> : null}
      {status === "success" && message ? <SuccessState message={message} /> : null}
      {status === "error" && message ? <ErrorState message={message} /> : null}
      {user && !user.email_verified ? <EmailVerificationNotice /> : null}
      {user?.email_verified ? (
        <SuccessState message="Your email is verified. You can continue to the workspace." />
      ) : null}
      <Link
        href={user ? "/" : "/login"}
        className="inline-flex h-10 items-center justify-center rounded-lg border border-zinc-700 bg-zinc-800 px-4 text-sm font-medium text-zinc-100 hover:bg-zinc-700"
      >
        {user ? "Go to dashboard" : "Sign in"}
      </Link>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<p className="p-10 text-sm text-zinc-400">Loading…</p>}>
      <VerifyEmailContent />
    </Suspense>
  );
}
