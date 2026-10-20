"use client";

import "lenis/dist/lenis.css";

import { ArrowDown, ArrowRight, BookOpen, Info, Play } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, type CSSProperties } from "react";

import { CompetitionPicker } from "@/components/competition/competition-picker";
import { Chapter, ChapterEyebrow, setupChapter, topBarHeight } from "@/components/landing/chapter";
import { STORY } from "@/components/landing/copy";
import { Counter, setupCounter } from "@/components/landing/counter";
import { HeroText, setupHeroText } from "@/components/landing/hero-text";
import { HudLabel } from "@/components/landing/hud-label";
import { ParticleCanvas, STAGES } from "@/components/landing/particle-canvas";
import { ReducedMotionFallback } from "@/components/landing/reduced-motion-fallback";
import { SectionHeader } from "@/components/ui/section-header";
import { usePrefersReducedMotion, whenIdle } from "@/lib/animation";
import type { LandingData } from "@/lib/landing";
import { cn } from "@/lib/utils";

const CONTAINER = "mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8";
const BUTTON =
  "inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold transition-[background-color,box-shadow,transform] focus-visible:ring-2 focus-visible:ring-ice-cyan focus-visible:outline-none";

const millions = (n: number) => `${(n / 1_000_000).toFixed(2)}M`;

/**
 * The home page: a scroll-driven story in five chapters, then the way into the app.
 *
 *   1. The anatomy of a delivery: a particle cricket ball, its seam, the headline.
 *   2. Every ball on the record: the ball breaks into a cloud and the deliveries count up.
 *   3. The probability ribbon: the cloud becomes a real match's win-probability curve.
 *   4. 10,000 futures: the ribbon fans out into simulated outcomes.
 *   5. Choose your game: the particles dissolve and the competition picker arrives.
 *
 * Lenis smooths the scrolling here only; GSAP ScrollTrigger pins each chapter and feeds the story's
 * progress to the canvas; both load after the page paints. Visitors who prefer reduced motion get
 * the same story as a still page (`ReducedMotionFallback`), switched by CSS before the first paint.
 */
export function LandingPage({ facts, ribbon, groups }: LandingData) {
  const reduced = usePrefersReducedMotion();
  const rootRef = useRef<HTMLDivElement>(null);
  const storyRef = useRef<HTMLDivElement>(null);
  const progress = useRef(0);

  useEffect(() => {
    if (reduced) return;
    let cancelled = false;
    let teardown = () => {};

    const start = async () => {
      const [{ gsap }, { ScrollTrigger }, { SplitText }, { default: Lenis }] = await Promise.all([
        import("gsap"),
        import("gsap/ScrollTrigger"),
        import("gsap/SplitText"),
        import("lenis"),
      ]);
      const root = rootRef.current;
      const story = storyRef.current;
      if (cancelled || !root || !story) return;
      gsap.registerPlugin(ScrollTrigger, SplitText);

      const lenis = new Lenis({
        // In-page links smooth-scroll too; targets keep clear of the top bar with scroll-margin.
        anchors: true,
        // Leave scrolling alone while a dialog (search, the phone menu) holds the page.
        prevent: (node) =>
          document.body.hasAttribute("data-scroll-locked") ||
          node.closest?.('[role="dialog"]') != null,
      });
      lenis.on("scroll", ScrollTrigger.update);
      const tick = (time: number) => lenis.raf(time * 1000);
      gsap.ticker.add(tick);
      gsap.ticker.lagSmoothing(0);

      const ctx = gsap.context(() => {
        const chapters = [...story.querySelectorAll<HTMLElement>("[data-chapter]")];
        // Pins first, in page order, so every later trigger measures the page with them.
        chapters.forEach((chapter) => setupChapter(ScrollTrigger, chapter));
        const chapterHeight = () => chapters[0]?.offsetHeight ?? window.innerHeight;
        ScrollTrigger.create({
          trigger: story,
          start: () => `top top+=${topBarHeight()}`,
          end: () => `+=${STAGES * chapterHeight()}`,
          invalidateOnRefresh: true,
          onUpdate: (self) => {
            progress.current = self.progress;
          },
        });

        for (const chapter of chapters) {
          chapter
            .querySelectorAll<HTMLElement>("[data-split]")
            .forEach((el) => setupHeroText(gsap, SplitText, el, chapter));
          chapter
            .querySelectorAll<HTMLElement>("[data-counter]")
            .forEach((el) => setupCounter(gsap, el, chapter));
          const reveal = chapter.querySelectorAll("[data-reveal]");
          if (reveal.length) {
            gsap.from(reveal, {
              opacity: 0,
              y: 18,
              duration: 0.7,
              ease: "power3.out",
              stagger: 0.08,
              scrollTrigger: {
                trigger: chapter,
                start: "top 55%",
                toggleActions: "play none none reverse",
              },
            });
          }
          const moments = chapter.querySelectorAll("[data-moment]");
          if (moments.length) {
            gsap.from(moments, {
              opacity: 0,
              scale: 0.85,
              duration: 0.6,
              ease: "back.out(1.6)",
              stagger: 0.25,
              delay: 0.3,
              scrollTrigger: {
                trigger: chapter,
                start: () => `top top+=${topBarHeight() + 1}`,
                toggleActions: "play none none reverse",
              },
            });
          }
        }

        // Chapter 5: the competition cards arrive one after another.
        const choose = root.querySelector("#choose");
        if (choose) {
          gsap.from(choose.querySelectorAll("li"), {
            opacity: 0,
            y: 24,
            duration: 0.6,
            ease: "power3.out",
            stagger: 0.05,
            scrollTrigger: { trigger: choose, start: "top 80%" },
          });
        }
      }, root);

      // Pins change the page's length: Lenis must measure again after every refresh, or it keeps
      // clamping scrolling to the old length.
      const remeasure = () => lenis.resize();
      ScrollTrigger.addEventListener("refresh", remeasure);
      ScrollTrigger.sort();
      ScrollTrigger.refresh();
      // The pins add scroll length above the picker: a "#choose" followed before they existed (a
      // quick click, or a link straight to it) now points too high, so go there again.
      const target = document.getElementById(window.location.hash.slice(1));
      if (target) lenis.scrollTo(target, { immediate: true });
      void document.fonts?.ready.then(() => {
        if (!cancelled) ScrollTrigger.refresh();
      });

      teardown = () => {
        ScrollTrigger.removeEventListener("refresh", remeasure);
        ctx.revert();
        gsap.ticker.remove(tick);
        lenis.destroy();
      };
    };
    // Load and set up the story once the page has painted and settled.
    const cancelStart = whenIdle(() => void start(), 1500);

    return () => {
      cancelled = true;
      cancelStart();
      teardown();
    };
  }, [reduced]);

  const { anatomy, record, ribbon: chapter3, futures, choose } = STORY;
  const [teamA, teamB] = [ribbon.teamA.short, ribbon.teamB.short];

  return (
    <div ref={rootRef} className="landing flex flex-col">
      {/* Chapters 1–4, animated. */}
      <div ref={storyRef} className="relative bg-void text-white motion-reduce:hidden">
        <div className="landing-stage sticky top-14 z-0 -mb-(--stage-h) h-(--stage-h)">
          <ParticleCanvas scrollProgress={progress} ribbon={ribbon.points} className="size-full" />
          {/* A soft vignette keeps the edges dark and the text legible over the particles. */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 bg-[radial-gradient(120%_90%_at_50%_45%,transparent_55%,var(--void)_100%)]"
          />
        </div>

        <Chapter id="anatomy">
          <div
            className={cn(
              CONTAINER,
              "flex h-full flex-col pt-8 sm:pt-12 lg:justify-center lg:pt-0",
            )}
          >
            <div className="max-w-xl lg:max-w-[44%]">
              <ChapterEyebrow number={anatomy.number} title={anatomy.eyebrow} />
              <HeroText
                as="h1"
                id="anatomy-heading"
                intro
                lines={[...anatomy.headline]}
                className="mt-5 text-[clamp(2.6rem,1.3rem+4.4vw,5.5rem)] leading-[1.02]"
              />
              <p
                className="landing-fade mt-5 max-w-lg text-sm leading-relaxed text-pretty text-white/70 max-sm:line-clamp-4 sm:text-base"
                style={{ "--delay": "550ms" } as CSSProperties}
              >
                {anatomy.body}
              </p>
              <div
                className="landing-fade mt-6 flex flex-wrap gap-3"
                style={{ "--delay": "750ms" } as CSSProperties}
              >
                <a
                  href="#choose"
                  className={cn(
                    BUTTON,
                    "bg-neon-turf text-void shadow-[0_0_28px_-6px_var(--neon-turf)] hover:-translate-y-px",
                  )}
                >
                  Choose a competition
                  <ArrowDown className="size-4" aria-hidden="true" />
                </a>
                <Link
                  href={ribbon.href}
                  className={cn(BUTTON, "landing-glass text-white hover:bg-white/10 max-sm:hidden")}
                >
                  <Play className="size-4" aria-hidden="true" />
                  Replay the {ribbon.title}
                </Link>
              </div>
            </div>
          </div>
          <div className="max-lg:absolute max-lg:inset-x-4 max-lg:bottom-20 max-lg:flex max-lg:justify-center max-lg:gap-2 lg:contents">
            <HudLabel label="Deliveries" value={millions(facts.deliveries)} dx={-1.2} dy={-1} />
            <HudLabel
              label="Matches"
              value={facts.matches.toLocaleString("en-US")}
              dx={1.15}
              dy={-0.55}
              delay={150}
            />
            <HudLabel
              label="Competitions"
              value={String(facts.competitions)}
              dx={0.95}
              dy={1}
              delay={300}
            />
          </div>
          <p
            aria-hidden="true"
            className="landing-fade absolute bottom-6 left-1/2 hidden -translate-x-1/2 items-center gap-3 font-mono text-[10px] tracking-[0.3em] text-white/50 uppercase lg:flex"
            style={{ "--delay": "1400ms" } as CSSProperties}
          >
            Scroll
            <span className="h-px w-10 bg-linear-to-r from-white/50 to-transparent" />
          </p>
        </Chapter>

        <Chapter id="record">
          <div
            className={cn(
              CONTAINER,
              "flex h-full flex-col pt-8 sm:pt-12 lg:justify-center lg:pt-0",
            )}
          >
            <div className="relative max-w-2xl">
              <div
                aria-hidden="true"
                className="absolute -inset-x-16 -inset-y-12 -z-10 bg-[radial-gradient(closest-side,var(--void)_40%,transparent)]"
              />
              <ChapterEyebrow number={record.number} title={record.eyebrow} />
              <p className="mt-6 font-sans text-[clamp(2.8rem,1.4rem+5.5vw,6.5rem)] leading-none font-semibold tracking-[-0.04em] text-white">
                <Counter value={facts.deliveries} />
              </p>
              <p className="mt-3 font-mono text-xs tracking-[0.2em] text-ice-cyan uppercase">
                deliveries, ball by ball
              </p>
              <HeroText
                id="record-heading"
                lines={[...record.headline]}
                className="mt-8 text-[clamp(1.9rem,1.1rem+2.8vw,3.5rem)] leading-[1.05]"
              />
              <p
                data-reveal=""
                className="mt-5 max-w-xl text-sm leading-relaxed text-pretty text-white/70 max-sm:line-clamp-4 sm:text-base"
              >
                {record.body(facts)}
              </p>
              <ul
                data-reveal=""
                aria-label="Matches per competition"
                className="mt-6 grid max-w-lg grid-cols-4 gap-x-4 gap-y-3 font-mono text-xs"
              >
                {facts.perCompetition.map((c) => (
                  <li key={c.id} className="flex flex-col gap-0.5">
                    <span className="text-white/60">{c.label}</span>
                    <span className="text-sm font-semibold text-white tabular-nums">
                      {c.matches.toLocaleString("en-US")}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Chapter>

        <Chapter id="ribbon">
          <div className={cn(CONTAINER, "pt-6 sm:pt-10")}>
            <ChapterEyebrow number={chapter3.number} title={chapter3.eyebrow} />
            <HeroText
              id="ribbon-heading"
              lines={[...chapter3.headline]}
              className="mt-4 text-[clamp(1.8rem,1.1rem+2.4vw,3.25rem)] leading-[1.05]"
            />
            <p
              data-reveal=""
              className="mt-3 max-w-2xl text-sm leading-relaxed text-pretty text-white/70 max-sm:line-clamp-3 sm:text-base"
            >
              {chapter3.body(ribbon)}
            </p>
            <p
              data-reveal=""
              className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[11px] text-white/70"
            >
              <span className="flex items-center gap-1.5">
                <span className="size-2 rounded-full bg-neon-turf" aria-hidden="true" />
                {teamA} ahead
              </span>
              <span className="flex items-center gap-1.5">
                <span className="size-2 rounded-full bg-pressure-amber" aria-hidden="true" />
                {teamB} ahead
              </span>
              <span>Model estimate</span>
              <Link href={ribbon.href} className="text-neon-turf underline underline-offset-2">
                Replay it ball by ball
              </Link>
            </p>
          </div>
          {/* The even-money line and the ends of the match, on the canvas's ribbon. */}
          <div
            aria-hidden="true"
            className="absolute top-[calc(var(--rib-y0)+var(--rib-h)/2)] left-(--rib-x0) w-(--rib-w) border-t border-dashed border-white/20"
          >
            <span className="absolute -top-5 right-0 font-mono text-[10px] text-white/50">50%</span>
          </div>
          <div
            aria-hidden="true"
            className="absolute top-[calc(var(--rib-y0)+var(--rib-h)+0.5rem)] left-(--rib-x0) flex w-(--rib-w) justify-between font-mono text-[10px] tracking-[0.18em] text-white/50 uppercase"
          >
            <span>First ball</span>
            <span>Last ball</span>
          </div>
          {ribbon.moments.map((m) => (
            <div
              key={m.label}
              data-moment=""
              className="landing-moment"
              style={{ "--t": m.t, "--wp": m.wp } as CSSProperties}
            >
              <span
                aria-hidden="true"
                className="absolute size-3 -translate-1/2 rounded-full border-2 border-void bg-white shadow-[0_0_16px_4px_var(--ice-cyan)]"
              />
              <div
                className={cn(
                  "landing-glass absolute bottom-4 w-max max-w-[11rem] rounded-xl px-3 py-2 sm:max-w-none",
                  // Cards end at their point on the right half (and on phones, where centred
                  // cards would collide); further left they centre on it.
                  m.t > 0.7
                    ? "right-0 translate-x-3"
                    : "right-0 translate-x-3 lg:right-auto lg:-translate-x-1/2",
                )}
              >
                <p className="text-sm font-semibold text-white">{m.label}</p>
                <p className="font-mono text-[11px] text-white/70">{m.detail}</p>
              </div>
            </div>
          ))}
        </Chapter>

        <Chapter id="futures">
          <div
            className={cn(
              CONTAINER,
              "flex h-full flex-col pt-8 sm:pt-12 lg:justify-center lg:pt-0",
            )}
          >
            <div className="max-w-xl lg:max-w-[42%]">
              <ChapterEyebrow number={futures.number} title={futures.eyebrow} />
              <HeroText
                id="futures-heading"
                lines={[...futures.headline]}
                className="mt-5 text-[clamp(1.9rem,1.1rem+2.8vw,3.5rem)] leading-[1.05]"
              />
              <p
                data-reveal=""
                className="mt-5 text-sm leading-relaxed text-pretty text-white/70 max-sm:line-clamp-3 sm:text-base"
              >
                {futures.body}
              </p>
              <dl data-reveal="" className="mt-6 flex gap-8 font-mono">
                <div className="flex flex-col-reverse gap-1">
                  <dt className="text-[10px] tracking-[0.18em] text-white/60 uppercase">
                    simulated matches
                  </dt>
                  <dd className="text-3xl font-semibold text-white">
                    <Counter value={10_000} />
                  </dd>
                </div>
                <div className="flex flex-col-reverse gap-1">
                  <dt className="text-[10px] tracking-[0.18em] text-white/60 uppercase">
                    to run them
                  </dt>
                  <dd className="text-3xl font-semibold text-white">
                    <span aria-hidden="true">≈</span>
                    <span className="sr-only">about </span>
                    <Counter value={0.5} decimals={1} /> s
                  </dd>
                </div>
              </dl>
              <Link
                data-reveal=""
                href="/ipl/simulator"
                className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-neon-turf underline-offset-4 hover:underline"
              >
                Open the simulator
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            </div>
          </div>
        </Chapter>

        <div aria-hidden="true" className="h-[40svh] bg-linear-to-b from-void to-background" />
      </div>

      {/* Chapters 1–4, still, for reduced motion. */}
      <ReducedMotionFallback facts={facts} ribbon={ribbon} className="hidden motion-reduce:block" />

      {/* Chapter 5: into the app. */}
      <div className={cn(CONTAINER, "flex flex-col gap-14 pt-4 pb-28 lg:pb-16")}>
        <section
          id="choose"
          aria-labelledby="choose-heading"
          className="flex scroll-mt-20 flex-col gap-6"
        >
          <ChapterEyebrow number={choose.number} title={choose.eyebrow} tone="app" />
          <SectionHeader
            id="choose-heading"
            title="Choose a competition"
            description="Each has its own matches, players, teams and models. Switch any time from the top bar."
            className="[&_h2]:text-headline"
          />
          <CompetitionPicker groups={groups} />
        </section>

        <section aria-labelledby="more-heading" className="flex flex-col gap-4">
          <SectionHeader id="more-heading" title="How it works" />
          <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <li>
              <Link
                href="/about"
                className="group flex h-full items-start gap-3 rounded-2xl border border-border bg-card p-5 shadow-elev-1 transition-[border-color,box-shadow] hover:border-primary/40 hover:shadow-elev-2"
              >
                <Info className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
                <span className="flex flex-col gap-1">
                  <span className="font-medium group-hover:text-primary">
                    About &amp; Methodology
                  </span>
                  <span className="text-sm text-muted-foreground">
                    Every number on the site, explained in plain terms.
                  </span>
                </span>
              </Link>
            </li>
            <li>
              <Link
                href="/writeup"
                className="group flex h-full items-start gap-3 rounded-2xl border border-border bg-card p-5 shadow-elev-1 transition-[border-color,box-shadow] hover:border-primary/40 hover:shadow-elev-2"
              >
                <BookOpen className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
                <span className="flex flex-col gap-1">
                  <span className="font-medium group-hover:text-primary">The write-up</span>
                  <span className="text-sm text-muted-foreground">
                    How the models were built and tested, and what did not work.
                  </span>
                </span>
              </Link>
            </li>
          </ul>
        </section>
      </div>
    </div>
  );
}
