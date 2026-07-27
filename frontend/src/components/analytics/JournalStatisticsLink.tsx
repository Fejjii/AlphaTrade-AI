import Link from "next/link";

export type JournalStatisticsLinkProps = {
  "data-testid"?: string;
  className?: string;
};

/** Smallest existing link pattern for Setups empty states. */
export function JournalStatisticsLink({
  "data-testid": testId = "setups-journal-statistics-link",
  className = "text-accent underline-offset-2 hover:underline",
}: JournalStatisticsLinkProps) {
  return (
    <Link href="/journal/statistics" className={className} data-testid={testId}>
      Journal statistics
    </Link>
  );
}
