"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { PaperModeBanner } from "@/components/PaperModeBanner";
import { ErrorState, SuccessState } from "@/components/states";
import { api, ApiError } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const response = await api.auth.requestPasswordReset(email);
      setMessage(response.message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Request failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 px-4 py-10">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-50">Forgot password</h1>
        <p className="text-sm text-zinc-400">
          Enter your email and we will send reset instructions if an account exists.
        </p>
      </div>
      <PaperModeBanner />
      <form onSubmit={onSubmit} className="space-y-4 rounded-xl border border-zinc-800 bg-zinc-900/70 p-5">
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        {error ? <ErrorState message={error} /> : null}
        {message ? <SuccessState message={message} /> : null}
        <Button type="submit" disabled={busy} className="w-full">
          Send reset link
        </Button>
      </form>
      <p className="text-sm text-zinc-400">
        <Link href="/login" className="text-emerald-400 hover:underline">
          Back to sign in
        </Link>
      </p>
    </div>
  );
}
