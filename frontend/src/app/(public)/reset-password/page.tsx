"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { PaperModeBanner } from "@/components/PaperModeBanner";
import { ErrorState, SuccessState } from "@/components/states";
import { api, ApiError } from "@/lib/api";

function ResetPasswordForm() {
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!token) {
      setError("Missing reset token. Open the link from your email.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const response = await api.auth.confirmPasswordReset(token, password);
      setMessage(response.message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Reset failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 px-4 py-10">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-50">Reset password</h1>
        <p className="text-sm text-zinc-400">Choose a new password (minimum 12 characters).</p>
      </div>
      <PaperModeBanner />
      <form onSubmit={onSubmit} className="space-y-4 rounded-xl border border-zinc-800 bg-zinc-900/70 p-5">
        <div className="space-y-2">
          <Label htmlFor="password">New password</Label>
          <Input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={12}
            required
          />
        </div>
        {error ? <ErrorState message={error} /> : null}
        {message ? <SuccessState message={message} /> : null}
        <Button type="submit" disabled={busy || !token} className="w-full">
          Update password
        </Button>
      </form>
      <p className="text-sm text-zinc-400">
        <Link href="/login" className="text-emerald-400 hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<p className="p-10 text-sm text-zinc-400">Loading…</p>}>
      <ResetPasswordForm />
    </Suspense>
  );
}
