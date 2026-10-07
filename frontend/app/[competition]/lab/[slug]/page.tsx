import type { Metadata } from "next";
import { notFound } from "next/navigation";

import {
  ClutchNoteView,
  MomentumNoteView,
  PressureNoteView,
  RivalriesNoteView,
} from "@/components/lab/notes";
import { getCompetition, isCompetitionId } from "@/lib/competitions";
import { LAB, type LabSlug, labEntry } from "@/lib/lab";
import { CompetitionLink } from "@/components/competition/competition-link";

const VIEWS: Record<LabSlug, () => React.ReactNode> = {
  momentum: MomentumNoteView,
  pressure: PressureNoteView,
  clutch: ClutchNoteView,
  rivalries: RivalriesNoteView,
};

export const dynamicParams = false;

// The notes are about the IPL; other competitions have no Analytics Lab yet, and their
// note pages render as not found. (Every competition lists the notes: if one returned no
// paths, Next.js would prerender none for any competition.)
export function generateStaticParams() {
  return LAB.map((note) => ({ slug: note.slug }));
}

export async function generateMetadata({
  params,
}: PageProps<"/[competition]/lab/[slug]">): Promise<Metadata> {
  const note = labEntry((await params).slug);
  return note ? { title: note.title, description: note.question } : {};
}

export default async function LabNotePage({ params }: PageProps<"/[competition]/lab/[slug]">) {
  const { competition, slug } = await params;
  const note = labEntry(slug);
  if (!note || !isCompetitionId(competition) || !getCompetition(competition).lab) notFound();
  const View = VIEWS[note.slug];
  return (
    <article className="flex flex-col gap-8">
      <nav aria-label="Breadcrumb" className="text-sm text-muted-foreground">
        <CompetitionLink href="/lab" className="hover:text-foreground">
          Analytics Lab
        </CompetitionLink>
        <span aria-hidden="true"> / </span>
        <span className="text-foreground">{note.title}</span>
      </nav>
      <header className="flex flex-col gap-3">
        <h1 className="text-3xl font-semibold tracking-tight">{note.title}</h1>
        <p className="max-w-3xl text-muted-foreground">{note.question}</p>
        <p className="max-w-3xl rounded-xl border border-primary/30 bg-primary/5 px-4 py-3 leading-relaxed">
          <span className="font-medium">Short answer: </span>
          {note.answer}
        </p>
      </header>
      <View />
    </article>
  );
}
