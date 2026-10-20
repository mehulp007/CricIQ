/**
 * Motion's animation features (springs, layout animations, gestures), in a chunk of their own:
 * `LazyMotion` loads them after the page has hydrated, so no page's first load carries them.
 */
import { domMax } from "motion/react";

export default domMax;
