/**
 * Friendly aliases over the types generated from the API's OpenAPI spec
 * (`schema.d.ts`, regenerated with `just api-types`). Never hand-write API shapes.
 */
import type { components } from "./schema";

type Schemas = components["schemas"];

export type Meta = Schemas["Meta"];
export type MatchSummary = Schemas["MatchSummary"];
export type MatchPage = Schemas["MatchPage"];
export type MatchDetail = Schemas["MatchDetail"];
export type TeamRef = Schemas["TeamRef"];
export type TeamScore = Schemas["TeamScore"];
export type Timeline = Schemas["Timeline"];
export type TimelineDelivery = Schemas["TimelineDelivery"];
export type TimelineInnings = Schemas["TimelineInnings"];
export type TimelinePlayer = Schemas["TimelinePlayer"];
export type TimelineSubstitution = Schemas["TimelineSubstitution"];
export type WinProbabilityModel = Schemas["WinProbabilityModel"];
export type ScoreProjectionModel = Schemas["ScoreProjectionModel"];

export type PlayerPage = Schemas["PlayerPage"];
export type PlayerListItem = Schemas["PlayerListItem"];
export type PlayerProfile = Schemas["PlayerProfile"];
export type PlayerSplits = Schemas["PlayerSplits"];
export type PlayerBio = Schemas["PlayerBio"];
export type PlayerRole = PlayerBio["role"];
export type TeamTag = Schemas["TeamTag"];
export type BattingSummary = Schemas["BattingSummary"];
export type BowlingSummary = Schemas["BowlingSummary"];
export type SeasonLine = Schemas["SeasonLine"];
export type PhaseBatting = Schemas["PhaseBatting"];
export type PhaseBowling = Schemas["PhaseBowling"];
export type Percentile = Schemas["Percentile"];
export type PercentileGroup = Schemas["PercentileGroup"];
export type BattingInnings = Schemas["BattingInnings"];
export type BowlingInnings = Schemas["BowlingInnings"];
export type DismissalCount = Schemas["DismissalCount"];
export type BattingSplitGroup = Schemas["BattingSplitGroup"];
export type BowlingSplitGroup = Schemas["BowlingSplitGroup"];
export type BattingSplitRow = Schemas["BattingSplitRow"];
export type BowlingSplitRow = Schemas["BowlingSplitRow"];
