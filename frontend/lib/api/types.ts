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
