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
export type Rating = Schemas["Rating"];
export type RatingGroup = Schemas["RatingGroup"];
export type RatingUnit = Rating["unit"];
export type SimilarPlayers = Schemas["SimilarPlayers"];
export type StyleGroup = Schemas["StyleGroup"];
export type SimilarPlayer = Schemas["SimilarPlayer"];
export type BattingInnings = Schemas["BattingInnings"];
export type BowlingInnings = Schemas["BowlingInnings"];
export type DismissalCount = Schemas["DismissalCount"];
export type BattingSplitGroup = Schemas["BattingSplitGroup"];
export type BowlingSplitGroup = Schemas["BowlingSplitGroup"];
export type BattingSplitRow = Schemas["BattingSplitRow"];
export type BowlingSplitRow = Schemas["BowlingSplitRow"];

export type MatchupDetail = Schemas["MatchupDetail"];
export type MatchupList = Schemas["MatchupList"];
export type MatchupListItem = Schemas["MatchupListItem"];
export type MatchupPlayer = Schemas["MatchupPlayer"];
export type MatchupNumbers = Schemas["MatchupNumbers"];
export type Interval = Schemas["Interval"];
export type NextBall = Schemas["NextBall"];
export type OutcomeProbability = Schemas["OutcomeProbability"];
export type MatchupPhase = NonNullable<MatchupDetail["phase"]>;
