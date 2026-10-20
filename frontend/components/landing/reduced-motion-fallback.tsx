import Link from "next/link";

import { ChapterEyebrow } from "@/components/landing/chapter";
import { STORY } from "@/components/landing/copy";
import { hash01 } from "@/lib/canvas-particles";
import type { LandingFacts, Ribbon } from "@/lib/landing";
import { cn } from "@/lib/utils";

const NEON = "var(--neon-turf)";
const ICE = "var(--ice-cyan)";
const AMBER = "var(--pressure-amber)";

function Section({
  id,
  number,
  eyebrow,
  heading,
  as: Heading = "h2",
  children,
  figure,
}: {
  id: string;
  number: string;
  eyebrow: string;
  heading: readonly string[];
  as?: "h1" | "h2";
  children: React.ReactNode;
  figure: React.ReactNode;
}) {
  return (
    <section
      aria-labelledby={`${id}-heading`}
      className="mx-auto grid w-full max-w-7xl grid-cols-1 items-center gap-10 px-4 py-16 lg:grid-cols-2 lg:px-8 lg:py-24"
    >
      <div className="flex min-w-0 flex-col gap-5">
        <ChapterEyebrow number={number} title={eyebrow} />
        <Heading
          id={`${id}-heading`}
          className="text-[clamp(2.2rem,1.3rem+3vw,4rem)] leading-[1.04] font-semibold tracking-[-0.035em] text-balance text-white"
        >
          {heading.map((line, i) => (
            <span key={line} className={cn("block", i > 0 && "text-white/55")}>
              {line}
            </span>
          ))}
        </Heading>
        {children}
      </div>
      <div className="min-w-0">{figure}</div>
    </section>
  );
}

/** A cricket ball: a lit sphere with its seam and the stitches either side. */
function BallFigure() {
  return (
    <svg
      viewBox="0 0 400 400"
      role="img"
      aria-label="A cricket ball, its seam picked out in light."
      className="mx-auto w-full max-w-sm"
    >
      <defs>
        <radialGradient id="static-ball" cx="38%" cy="32%" r="70%">
          <stop offset="0" stopColor="#DCE6F2" stopOpacity="0.5" />
          <stop offset="0.6" stopColor="#DCE6F2" stopOpacity="0.08" />
          <stop offset="1" stopColor="#DCE6F2" stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="200" cy="200" r="150" fill="url(#static-ball)" />
      <circle cx="200" cy="200" r="150" fill="none" stroke="#DCE6F2" strokeOpacity="0.25" />
      <path d="M150 58 C 245 120, 245 280, 150 342" fill="none" stroke={NEON} strokeWidth="3" />
      <path
        d="M140 62 C 232 124, 232 276, 140 338"
        fill="none"
        stroke={NEON}
        strokeOpacity="0.6"
        strokeDasharray="2 7"
        strokeWidth="5"
      />
      <path
        d="M160 54 C 258 116, 258 284, 160 346"
        fill="none"
        stroke={NEON}
        strokeOpacity="0.6"
        strokeDasharray="2 7"
        strokeWidth="5"
      />
    </svg>
  );
}

/** Every ball as a field of points. */
function CloudFigure() {
  const dots = Array.from({ length: 480 }, (_, i) => ({
    x: ((i % 30) + hash01(i, 7)) * (400 / 30),
    y: (Math.floor(i / 30) + hash01(i, 13)) * (260 / 16),
    o: 0.15 + 0.6 * hash01(i, 19),
    c: i % 11 === 0 ? ICE : i % 17 === 0 ? NEON : "#DCE6F2",
  }));
  return (
    <svg
      viewBox="0 0 400 260"
      role="img"
      aria-label="A field of points, one for many deliveries."
      className="w-full"
    >
      {dots.map((d, i) => (
        <circle key={i} cx={d.x} cy={d.y} r="1.6" fill={d.c} fillOpacity={d.o} />
      ))}
    </svg>
  );
}

/** The match's win-probability curve, above the even-money line where team A is ahead. */
function RibbonFigure({ ribbon }: { ribbon: Ribbon }) {
  const X0 = 16;
  const W = 968;
  const Y0 = 20;
  const H = 320;
  const at = (t: number, wp: number) => [X0 + t * W, Y0 + (1 - wp) * H] as const;
  const path = ribbon.points
    .map(([t, wp], i) => `${i ? "L" : "M"}${at(t, wp)[0].toFixed(1)} ${at(t, wp)[1].toFixed(1)}`)
    .join(" ");
  return (
    <figure className="flex flex-col gap-3">
      <svg
        viewBox="0 0 1000 360"
        role="img"
        aria-label={`${ribbon.teamA.short}'s chance of winning through the ${ribbon.title}, ball by ball: above the middle line ${ribbon.teamA.short} were ahead, below it ${ribbon.teamB.short}.`}
        className="w-full"
      >
        <defs>
          <clipPath id="static-ahead">
            <rect x="0" y="0" width="1000" height={Y0 + H / 2} />
          </clipPath>
          <clipPath id="static-behind">
            <rect x="0" y={Y0 + H / 2} width="1000" height={H} />
          </clipPath>
        </defs>
        <line
          x1={X0}
          x2={X0 + W}
          y1={Y0 + H / 2}
          y2={Y0 + H / 2}
          stroke="#DCE6F2"
          strokeOpacity="0.3"
          strokeDasharray="6 6"
        />
        <path d={path} fill="none" stroke={NEON} strokeWidth="3" clipPath="url(#static-ahead)" />
        <path d={path} fill="none" stroke={AMBER} strokeWidth="3" clipPath="url(#static-behind)" />
        {ribbon.moments.map((m) => {
          const [x, y] = at(m.t, m.wp);
          return <circle key={m.label} cx={x} cy={y} r="7" fill="#fff" />;
        })}
      </svg>
      <figcaption className="flex flex-wrap gap-x-6 gap-y-2 font-mono text-xs text-white/70">
        {ribbon.moments.map((m) => (
          <span key={m.label}>
            <span className="text-white">{m.label}</span> · {m.detail}
          </span>
        ))}
        <span>Model estimate</span>
      </figcaption>
    </figure>
  );
}

/** Simulated outcomes fanning out from one point into a bell. An illustration. */
function FanFigure() {
  const strands = Array.from({ length: 48 }, (_, i) => {
    const u = (i + 0.5) / 48;
    // Normal quantiles (approximately), so the strands bunch in the middle.
    const z = Math.sqrt(-2 * Math.log(Math.min(u, 1 - u))) * (u < 0.5 ? -1 : 1);
    return 130 + (z / 2.6) * 110;
  });
  const bell = Array.from({ length: 41 }, (_, i) => {
    const y = 20 + i * 5.5;
    const z = (y - 130) / 40;
    return `${i ? "L" : "M"}${(370 + 26 * Math.exp((-z * z) / 2)).toFixed(1)} ${y.toFixed(1)}`;
  }).join(" ");
  return (
    <svg
      viewBox="0 0 400 260"
      role="img"
      aria-label="An illustration: simulated matches fanning out from one point into a bell-shaped spread of results."
      className="w-full"
    >
      {strands.map((y, i) => (
        <path
          key={i}
          d={`M20 130 C 160 130, 220 ${y}, 360 ${y}`}
          fill="none"
          stroke={ICE}
          strokeOpacity="0.35"
        />
      ))}
      <path d={bell} fill="none" stroke={NEON} strokeWidth="2" />
      <circle cx="20" cy="130" r="5" fill={NEON} />
    </svg>
  );
}

/**
 * The landing story without motion, for visitors who prefer reduced motion: the same chapters and
 * words, each with a still illustration, in an ordinary scrolling page.
 */
export function ReducedMotionFallback({
  facts,
  ribbon,
  className,
}: {
  facts: LandingFacts;
  ribbon: Ribbon;
  className?: string;
}) {
  const { anatomy, record, ribbon: chapter3, futures } = STORY;
  return (
    <div className={cn("bg-void text-white", className)}>
      <Section
        id="static-anatomy"
        as="h1"
        number={anatomy.number}
        eyebrow={anatomy.eyebrow}
        heading={anatomy.headline}
        figure={<BallFigure />}
      >
        <p className="max-w-xl leading-relaxed text-white/70">{anatomy.body}</p>
        <dl className="flex flex-wrap gap-3 font-mono">
          {[
            ["Deliveries", facts.deliveries.toLocaleString("en-US")],
            ["Matches", facts.matches.toLocaleString("en-US")],
            ["Competitions", String(facts.competitions)],
          ].map(([label, value]) => (
            <div
              key={label}
              className="landing-glass flex flex-col-reverse gap-0.5 rounded-xl px-3 py-2"
            >
              <dt className="text-[10px] tracking-[0.18em] text-white/65 uppercase">{label}</dt>
              <dd className="text-lg font-semibold">{value}</dd>
            </div>
          ))}
        </dl>
        <a
          href="#choose"
          className="w-fit rounded-lg bg-neon-turf px-4 py-2 text-sm font-semibold text-void"
        >
          Choose a competition
        </a>
      </Section>
      <Section
        id="static-record"
        number={record.number}
        eyebrow={record.eyebrow}
        heading={record.headline}
        figure={<CloudFigure />}
      >
        <p className="font-mono text-5xl font-semibold tracking-tight">
          {facts.deliveries.toLocaleString("en-US")}
          <span className="mt-1 block text-xs tracking-[0.2em] text-ice-cyan uppercase">
            deliveries, ball by ball
          </span>
        </p>
        <p className="max-w-xl leading-relaxed text-white/70">{record.body(facts)}</p>
      </Section>
      <Section
        id="static-ribbon"
        number={chapter3.number}
        eyebrow={chapter3.eyebrow}
        heading={chapter3.headline}
        figure={<RibbonFigure ribbon={ribbon} />}
      >
        <p className="max-w-xl leading-relaxed text-white/70">{chapter3.body(ribbon)}</p>
        <Link href={ribbon.href} className="w-fit text-sm text-neon-turf underline">
          Replay this final ball by ball
        </Link>
      </Section>
      <Section
        id="static-futures"
        number={futures.number}
        eyebrow={futures.eyebrow}
        heading={futures.headline}
        figure={<FanFigure />}
      >
        <p className="max-w-xl leading-relaxed text-white/70">{futures.body}</p>
        <p className="font-mono text-sm text-white/70">
          <span className="text-2xl font-semibold text-white">10,000</span> simulated matches ·{" "}
          <span className="text-2xl font-semibold text-white">about 0.5 s</span>
        </p>
      </Section>
      <div aria-hidden="true" className="h-40 bg-linear-to-b from-void to-background" />
    </div>
  );
}
