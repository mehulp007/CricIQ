import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import {
  ClutchNoteView,
  MomentumNoteView,
  PressureNoteView,
  RivalriesNoteView,
} from "@/components/lab/notes";
import { LAB, type LabSlug, labEntry } from "@/lib/lab";

const VIEWS: Record<LabSlug, () => React.ReactNode> = {
  momentum: MomentumNoteView,
  pressure: PressureNoteView,
  clutch: ClutchNoteView,
  rivalries: RivalriesNoteView,
};

export const dynamicParams = false;

export function generateStaticParams() {
  return LAB.map((note) => ({ slug: note.slug }));
}

export async function generateMetadata({ params }: PageProps<"/lab/[slug]">): Promise<Metadata> {
  const note = labEntry((await params).slug);
  return note ? { title: note.title, description: note.question } : {};
}

export default async function LabNotePage({ params }: PageProps<"/lab/[slug]">) {
  const note = labEntry((await params).slug);
  if (!note) notFound();
  const View = VIEWS[note.slug];
  return (
    <article className="flex flex-col gap-8">
      <nav aria-label="Breadcrumb" className="text-sm text-muted-foreground">
        <Link href="/lab" className="hover:text-foreground">
          Analytics Lab
        </Link>
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
