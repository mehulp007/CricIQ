import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { RecordTable } from "@/components/records/record-table";
import { Breadcrumbs } from "@/components/ui/breadcrumbs";
import { CoverageNote } from "@/components/ui/coverage-note";
import { EmptyState } from "@/components/ui/empty-state";
import { FilterBar, type FilterField } from "@/components/ui/filter-bar";
import { PageHeader } from "@/components/ui/page-header";
import { ApiError, getMeta, getRecord } from "@/lib/api/client";
import {
  competitionPath,
  getCompetition,
  isCompetitionId,
  type CompetitionId,
} from "@/lib/competitions";
import { GROUP_LABELS, PAGE_SIZE, pageOf, recordQuery } from "@/lib/records";
import { toSearchParams, withParam } from "@/lib/url";

export async function generateMetadata({
  params,
}: PageProps<"/[competition]/records/[key]">): Promise<Metadata> {
  const { competition, key } = await params;
  if (!isCompetitionId(competition)) return {};
  try {
    const { record } = await getRecord(competition, key, new URLSearchParams({ limit: "1" }));
    const c = getCompetition(competition);
    return {
      title: `${c.label}: ${record.label}`,
      description:
        `${record.label} in ${c.collective}, ranked from the ball-by-ball data. ${record.description}`.trim(),
    };
  } catch {
    return {};
  }
}

export default async function RecordPage({
  params,
  searchParams,
}: PageProps<"/[competition]/records/[key]">) {
  const { competition: id, key } = await params;
  const competition = id as CompetitionId;
  const c = getCompetition(competition);
  const raw = await searchParams;
  let data;
  try {
    data = await getRecord(competition, key, recordQuery(raw, { wicket: true }));
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 422)) notFound();
    throw error;
  }
  const meta = await getMeta(competition);
  const { record } = data;
  const page = pageOf(raw);
  const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));

  const seasons = meta.seasons
    .filter((s) => s.matches > 0)
    .map((s) => ({ value: String(s.year), label: s.label }));
  const teams = meta.franchises.map((f) => ({ value: f.franchise_id, label: f.name }));
  const side = c.teamType === "national" ? "side" : "team";
  const fields: FilterField[] = [
    { param: "from", label: "From season", all: "First season", choices: seasons, width: "w-36" },
    { param: "to", label: "To season", all: "Latest season", choices: seasons, width: "w-36" },
    {
      param: "team",
      label: side === "side" ? "Side" : "Team",
      all: `All ${side}s`,
      choices: teams,
      width: "w-52",
    },
    { param: "opponent", label: "Against", all: "Any opponent", choices: teams, width: "w-52" },
    {
      param: "venue",
      label: "Ground",
      all: "All grounds",
      choices: [...meta.venues]
        .sort((a, b) => b.matches - a.matches)
        .map((v) => ({ value: v.venue_id, label: `${v.name} (${v.matches})` })),
      width: "w-60",
    },
  ];
  if (record.key === "highest-partnerships") {
    fields.push({
      param: "wicket",
      label: "Wicket",
      all: "Any wicket",
      choices: Array.from({ length: 10 }, (_, i) => ({
        value: String(i + 1),
        label: `${i + 1}${["st", "nd", "rd"][i] ?? "th"} wicket`,
      })),
      width: "w-36",
    });
  }

  const pageHref = (n: number) => {
    const next = withParam(toSearchParams(raw), "page", n > 1 ? String(n) : null);
    const query = next.toString();
    return competitionPath(competition, `/records/${record.key}${query ? `?${query}` : ""}`);
  };

  return (
    <div className="flex flex-col gap-6">
      <Breadcrumbs items={[{ label: "Records", href: "/records" }, { label: record.label }]} />
      <PageHeader
        eyebrow={`${c.label} · ${GROUP_LABELS[record.group]}`}
        title={record.label}
        description={
          <>
            {record.description}
            {record.qualification && (
              <>
                {record.description ? " " : ""}
                {record.qualification}.
              </>
            )}
            {record.model && " Model estimate: built from CricIQ's win-probability model."} Equal
            figures share a rank.
          </>
        }
      />
      <div className="flex flex-col gap-3">
        <FilterBar fields={fields} />
        <CoverageNote competition={c.label} coverage={data.coverage} />
      </div>
      {data.entries.length === 0 ? (
        <EmptyState
          title="Nothing matches these filters"
          description="Try a wider season range, another side or any ground."
        />
      ) : (
        <>
          <RecordTable record={record} entries={data.entries} />
          {pages > 1 && (
            <nav aria-label="Pages" className="flex items-center justify-between gap-3 text-sm">
              {page > 1 ? (
                <Link
                  href={pageHref(page - 1)}
                  className="text-primary underline-offset-4 hover:underline"
                >
                  Previous {PAGE_SIZE}
                </Link>
              ) : (
                <span />
              )}
              <span className="text-muted-foreground">
                Page {page} of {pages} · {data.total.toLocaleString("en-US")} entries
              </span>
              {page < pages ? (
                <Link
                  href={pageHref(page + 1)}
                  className="text-primary underline-offset-4 hover:underline"
                >
                  Next {PAGE_SIZE}
                </Link>
              ) : (
                <span />
              )}
            </nav>
          )}
        </>
      )}
    </div>
  );
}
