import type { Metadata } from "next";

import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata: Metadata = {
  title: "About & Methodology",
  description: "Data sources, modelling principles and limitations behind CricIQ.",
};

const PRINCIPLES: { title: string; body: string }[] = [
  {
    title: "No peeking into the future",
    body: "Every player, venue and form feature is computed only from matches played before the moment being analysed. Models are trained on older seasons and tested on the most recent ones.",
  },
  {
    title: "Calibrated, not just accurate",
    body: "A 70% win probability should come true about 70% of the time. Models are judged on log loss, Brier score and calibration, not only on accuracy.",
  },
  {
    title: "Honest about sample size",
    body: "Small head-to-head samples are shown with their size and adjusted toward sensible baselines, instead of being presented as certainties.",
  },
  {
    title: "Estimates, not guarantees",
    body: "All predictions and simulations are statistical model estimates based on historical data. CricIQ is a sports analytics project and is not intended for betting.",
  },
];

export default function AboutPage() {
  return (
    <div className="flex max-w-3xl flex-col gap-10">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight">About &amp; Methodology</h1>
        <p className="mt-3 leading-relaxed text-muted-foreground">
          CricIQ is an open-source cricket analytics platform that takes IPL data from raw
          ball-by-ball records through data engineering, feature engineering, machine learning and
          explainability, all the way to this interface.
        </p>
      </header>

      <section className="flex flex-col gap-4">
        <h2 className="text-xl font-semibold tracking-tight">Principles</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {PRINCIPLES.map((p) => (
            <Card key={p.title} className="bg-card/70">
              <CardHeader>
                <CardTitle className="text-base">{p.title}</CardTitle>
              </CardHeader>
              <CardContent className="text-sm leading-relaxed text-muted-foreground">
                {p.body}
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-xl font-semibold tracking-tight">Models</h2>
        <p className="leading-relaxed text-muted-foreground">
          The win probability in every replay comes from two gradient-boosted tree models, tested on
          the two most recent seasons and backtested season by season.{" "}
          <Link href="/models" className="text-primary underline-offset-4 hover:underline">
            Model Insights
          </Link>{" "}
          shows the evaluation, the features that were tried and rejected, and the limitations.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-xl font-semibold tracking-tight">Data &amp; attribution</h2>
        <p className="leading-relaxed text-muted-foreground">
          Ball-by-ball match data comes from{" "}
          <a
            href="https://cricsheet.org"
            className="text-primary underline-offset-4 hover:underline"
            target="_blank"
            rel="noreferrer"
          >
            Cricsheet
          </a>{" "}
          and is used under the Open Data Commons Attribution License (ODC-BY). Player attributes
          such as batting hand and bowling style come from a curated reference file maintained in
          the project repository.
        </p>
        <p className="leading-relaxed text-muted-foreground">
          CricIQ is an independent portfolio project. It is not affiliated with, endorsed by, or
          connected to the Indian Premier League, the BCCI or any franchise. Team names are used
          only to describe historical matches.
        </p>
      </section>
    </div>
  );
}
