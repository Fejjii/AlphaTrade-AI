import { PaperModeBanner } from "@/components/PaperModeBanner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function RiskSettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Risk Settings</h1>
        <p className="text-sm text-zinc-400">
          Deterministic risk rules are enforced server-side. UI overrides are not enabled in this slice.
        </p>
      </div>
      <PaperModeBanner />
      <Card>
        <CardHeader>
          <CardTitle>Risk policy posture</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-zinc-400">
          <p>Risk blocks from the engine are final unless future settings explicitly allow changes.</p>
          <p>Kill switch and approval gates remain visible on trading-related pages.</p>
          <p>Real trading remains disabled — only paper workflows are available.</p>
        </CardContent>
      </Card>
    </div>
  );
}
