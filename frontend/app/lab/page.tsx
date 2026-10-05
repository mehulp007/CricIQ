import { ArrowRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { LAB } from "@/lib/lab";

export const metadata: Metadata = {
  title: "Analytics Lab",
  description:
    "Research notes on IPL cricket: is momentum real, what pressure does to batting, and whether clutch is a skill, each answered with a test that could have gone the other way.",
};

export default function LabPage() {
  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">Analytics Lab</h1>
        <p className="max-w-3xl text-muted-foreground">
          Questions about cricket that people argue about, answered with every IPL ball since 2008.
          Each note states its method, shows its uncertainty and reports the answer even when it is
          &quot;no&quot;.
        </p>
      </header>
      <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {LAB.map((note) => (
          <li key={note.slug} className="flex">
            <Link
              href={`/lab/${note.slug}`}
              className="group flex w-full flex-col gap-3 rounded-2xl border border-border bg-card/70 p-5 transition-colors hover:border-primary/40"
            >
              <span className="flex items-center justify-between gap-3">
                <span className="text-lg font-semibold tracking-tight">{note.title}</span>
                <ArrowRight
                  className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary"
                  aria-hidden="true"
                />
              </span>
              <span className="text-sm leading-relaxed text-muted-foreground">{note.question}</span>
              <span className="mt-auto border-t border-border pt-3 text-sm leading-relaxed">
                {note.answer}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
