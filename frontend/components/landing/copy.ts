import type { LandingFacts, Ribbon } from "@/lib/landing";

/** The landing story's words, shared by the animated story and the reduced-motion page. */

const count = (n: number) => n.toLocaleString("en-US");
const WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"];
/** Numbers under ten in words, as in prose. */
const say = (n: number) => WORDS[n] ?? count(n);

export const STORY = {
  anatomy: {
    number: "01",
    eyebrow: "The anatomy of a delivery",
    headline: ["Decode the game.", "Predict the next move."],
    body: "Every delivery of the IPL, men's T20 internationals, ODIs and Tests, and the BBL, PSL, CPL and SA20, as interactive analytics: replay any match with each side's chance of winning after every ball, measure any career against par, and read any rivalry without over-reading small samples.",
  },
  record: {
    number: "02",
    eyebrow: "Every ball on the record",
    headline: ["Nothing assumed.", "Nothing hallucinated."],
    body: (facts: LandingFacts) =>
      `Every delivery of ${say(facts.competitions)} men's competitions since ${facts.firstSeason}: ${count(facts.matches)} matches, recorded ball by ball by Cricsheet and checked against known scorecards, results and league tables before anything is built on them.`,
  },
  ribbon: {
    number: "03",
    eyebrow: "The probability ribbon",
    headline: ["Every ball changes the story.", "Follow the pressure."],
    body: (ribbon: Ribbon) =>
      `The ${ribbon.title}, ${ribbon.teamA.name} against ${ribbon.teamB.name}: ${ribbon.teamA.short}'s chance of winning before the first ball and after each of the ${ribbon.points.length - 1} deliveries. ${ribbon.result}.`,
  },
  futures: {
    number: "04",
    eyebrow: "10,000 futures in half a second",
    headline: ["Every outcome.", "Every edge case.", "Simulated."],
    body: "Pick two limited-overs sides and the simulator plays them 10,000 times, ball by ball, in about half a second: how often each side wins and how the scores spread, not a single guess. Stop any replay, change the score, and see what follows.",
  },
  choose: {
    number: "05",
    eyebrow: "Choose your game",
  },
} as const;
