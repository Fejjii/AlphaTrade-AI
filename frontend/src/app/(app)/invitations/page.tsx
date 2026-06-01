"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState, SuccessState } from "@/components/states";
import { api, ApiError } from "@/lib/api";
import type { MembershipRole, OrganizationInvitation } from "@/lib/api/types";

export default function InvitationsPage() {
  const [invitations, setInvitations] = useState<OrganizationInvitation[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<MembershipRole>("trader");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const response = await api.organizations.listInvitations();
      setInvitations(response.invitations);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load invitations.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function createInvite(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await api.organizations.createInvitation({ email, role });
      setEmail("");
      setMessage("Invitation created.");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create invitation.");
    } finally {
      setBusy(false);
    }
  }

  async function revoke(id: string) {
    try {
      await api.organizations.revokeInvitation(id);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not revoke invitation.");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Team invitations</h1>
        <p className="text-sm text-zinc-400">Owners can invite traders and viewers (groundwork slice).</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Invite member</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={createInvite} className="grid gap-3 md:grid-cols-3">
            <div className="space-y-2 md:col-span-2">
              <Label htmlFor="invite-email">Email</Label>
              <Input
                id="invite-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="invite-role">Role</Label>
              <select
                id="invite-role"
                className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
                value={role}
                onChange={(e) => setRole(e.target.value as MembershipRole)}
              >
                <option value="trader">Trader</option>
                <option value="viewer">Viewer</option>
              </select>
            </div>
            <Button type="submit" disabled={busy} className="md:col-span-3">
              Send invitation
            </Button>
          </form>
          {error ? <ErrorState className="mt-3" message={error} /> : null}
          {message ? <SuccessState className="mt-3" message={message} /> : null}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Pending and recent invitations</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {invitations.length === 0 ? (
            <p className="text-zinc-400">No invitations yet.</p>
          ) : (
            invitations.map((inv) => (
              <div
                key={inv.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-zinc-800 px-3 py-2"
              >
                <div>
                  <p className="font-medium text-zinc-100">{inv.email}</p>
                  <p className="text-zinc-400">
                    {inv.role} · {inv.is_pending ? "pending" : inv.accepted_at ? "accepted" : "closed"}
                  </p>
                </div>
                {inv.is_pending ? (
                  <Button type="button" size="sm" variant="secondary" onClick={() => void revoke(inv.id)}>
                    Revoke
                  </Button>
                ) : null}
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
