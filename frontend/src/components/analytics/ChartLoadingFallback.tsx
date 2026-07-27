"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

type ChartLoadingFallbackProps = {
  title: string;
};

/** Chart-frame skeleton shown while Recharts bundles load on the Performance tab. */
export function ChartLoadingFallback({ title }: ChartLoadingFallbackProps) {
  return (
    <Card data-testid="chart-loading-fallback">
      <CardHeader className="space-y-2 pb-3">
        <CardTitle className="text-base font-medium">{title}</CardTitle>
        <Skeleton className="h-4 w-2/3" />
      </CardHeader>
      <CardContent>
        <Skeleton className="h-[220px] w-full rounded-card" aria-label={`Loading ${title}`} />
      </CardContent>
    </Card>
  );
}
