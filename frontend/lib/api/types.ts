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

export type TeamsOverview = Schemas["TeamsOverview"];
export type FranchiseSummary = Schemas["FranchiseSummary"];
export type SeasonChampion = Schemas["SeasonChampion"];
export type LeagueTrends = Schemas["LeagueTrends"];
export type SeasonTrend = Schemas["SeasonTrend"];
export type Rate = Schemas["Rate"];
export type TeamRecord = Schemas["Record"];
export type Standings = Schemas["Standings"];
export type StandingRow = Schemas["StandingRow"];
export type Finish = StandingRow["finish"];
export type TeamProfile = Schemas["TeamProfile"];
export type TeamSeason = Schemas["TeamSeason"];
export type RecordGroup = Schemas["RecordGroup"];
export type TeamPhase = Schemas["TeamPhase"];
export type PhaseLine = Schemas["PhaseLine"];
export type TeamScoring = Schemas["TeamScoring"];
export type TeamTotal = Schemas["TeamTotal"];
export type TeamBatter = Schemas["TeamBatter"];
export type TeamBowler = Schemas["TeamBowler"];
export type OpponentRecord = Schemas["OpponentRecord"];
export type VenueRecord = Schemas["VenueRecord"];
export type Swing = Schemas["Swing"];
export type HeadToHead = Schemas["TeamHeadToHead"];
export type H2HRecord = Schemas["H2HRecord"];
export type H2HExpectation = Schemas["H2HExpectation"];
export type H2HPlayer = Schemas["H2HPlayer"];

export type SimPlayer = Schemas["SimPlayer"];
export type SquadPlayer = Schemas["SquadPlayer"];
export type SimSquad = Schemas["SimSquad"];
export type SimSeason = Schemas["SimSeason"];
export type SimSeasonTeam = Schemas["SimSeasonTeam"];
export type SimulationRequest = Schemas["SimulationRequest"];
export type SimulationResult = Schemas["SimulationResult"];
export type SimSideResult = Schemas["SideResult"];
export type SimBatter = Schemas["SimBatter"];
export type SimBowler = Schemas["SimBowler"];
export type SimDistribution = Schemas["Distribution"];
export type StateRequest = Schemas["StateRequest"];
export type StateResult = Schemas["StateResult"];
export type ChaseWhatIf = Schemas["ChaseWhatIf"];
export type ChaseOutcome = Schemas["ChaseOutcome"];
export type ChaseSides = Schemas["ChaseSides"];
export type ChaseSide = Schemas["ChaseSide"];
export type ChaseCalculation = Schemas["ChaseCalculation"];

export type CompetitionList = Schemas["CompetitionList"];
export type CompetitionScope = Schemas["CompetitionScope"];
export type PlayerCareers = Schemas["PlayerCareers"];
export type CareerLine = Schemas["CareerLine"];
export type CareerRatings = Schemas["CareerRatings"];
export type CareerRatingsLine = Schemas["CareerRatingsLine"];
export type CareerRating = Schemas["CareerRating"];

export type SeriesPage = Schemas["SeriesPage"];
export type SeriesSummary = Schemas["SeriesSummary"];
export type SeriesTeam = Schemas["SeriesTeam"];
export type SeriesDetail = Schemas["SeriesDetail"];
export type SeriesMatch = Schemas["SeriesMatch"];
export type SeriesRound = Schemas["SeriesRound"];
export type SeriesStanding = Schemas["SeriesStanding"];
export type SeriesBatter = Schemas["SeriesBatter"];
export type SeriesBowler = Schemas["SeriesBowler"];
export type DecisivePlayer = Schemas["DecisivePlayer"];
export type SeriesRecord = Schemas["SeriesRecord"];
export type SeriesRef = Schemas["SeriesRef"];
export type CompetitionInfo = Schemas["CompetitionInfo"];
export type MetaFeatures = Schemas["Features"];
