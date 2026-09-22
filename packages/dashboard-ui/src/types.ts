/**
 * Re-exports and aliases for generated NSwag client types.
 * Single source of truth is src/api/client.ts.
 */
import type {
  IssueSchema,
  IssueSchemaStatus,
  IssueSchemaType,
  IssueSchemaPriority,
  MilestoneSchema,
  MilestoneSchemaStatus,
  RiskSchema,
  RiskSchemaSeverity,
  RiskSchemaStatus,
  SpikeSchema,
  SpikeSchemaStatus,
  SessionSchema,
  DecisionSchema,
  KBArticleSchema,
  DashboardMetricsSchema,
  FullDashboardDataSchema,
  SearchResultItem,
  SearchResponse,
  KBGraphSchema,
  KBGraphNode,
  KBGraphEdge,
} from './api/client';

export type Issue = IssueSchema;
export type IssueStatus = IssueSchemaStatus;
export type IssueType = IssueSchemaType;
export type IssuePriority = IssueSchemaPriority;

export type Milestone = MilestoneSchema;
export type MilestoneStatus = MilestoneSchemaStatus;

export type Risk = RiskSchema;
export type RiskSeverity = RiskSchemaSeverity;
export type RiskStatus = RiskSchemaStatus;

export type Spike = SpikeSchema;
export type SpikeStatus = SpikeSchemaStatus;

export type Session = SessionSchema;
export type Decision = DecisionSchema;
export type KBArticle = KBArticleSchema;
export type DashboardMetrics = DashboardMetricsSchema;
export type FullDashboardData = FullDashboardDataSchema;

export type {
  SearchResultItem,
  SearchResponse,
  KBGraphSchema,
  KBGraphNode,
  KBGraphEdge,
};
