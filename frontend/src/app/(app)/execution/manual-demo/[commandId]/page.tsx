"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useParams } from "next/navigation";
import { ManualDemoDetail } from "@/components/settings/ManualDemoDetail";

export default function ManualDemoCommandPage() {
  const { user, organization } = useAuth();
  const { commandId } = useParams<{ commandId: string }>();
  return (
    <ManualDemoDetail
      key={`${organization?.id}:${user?.id}:${commandId}`}
      commandId={commandId}
    />
  );
}
