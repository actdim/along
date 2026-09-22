// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import { DashboardApiClient } from './client';
import { DashboardApiService } from '../services/apiService';
import DOMPurify from 'dompurify';
import type {
  Issue,
  FullDashboardData,
  DashboardMetrics,
  SearchResultItem,
} from '../types';

describe('DashboardApiClient and DTO Type Safety', () => {
  it('instantiates DashboardApiClient with default settings', () => {
    const client = new DashboardApiClient();
    expect(client).toBeDefined();
    expect(typeof client.getFullData).toBe('function');
    expect(typeof client.getMetrics).toBe('function');
    expect(typeof client.listIssues).toBe('function');
    expect(typeof client.searchKb).toBe('function');
  });

  it('validates FullDashboardData structure compatibility', () => {
    const mockMetrics: DashboardMetrics = {
      total_issues: 10,
      open_issues: 5,
      in_progress_issues: 2,
      blocked_issues: 1,
      done_issues: 2,
      completion_pct: 20,
      bug_debt_ratio: 0.5,
      active_risks: 1,
      active_milestones: 2,
      total_kb_articles: 8,
      total_decisions: 12,
      total_sessions: 4,
      by_status: {
        open: 5,
        in_progress: 2,
        blocked: 1,
        done: 2,
        superseded: 0,
        cancelled: 0,
        duplicate: 0,
      },
      by_type: { feat: 5, bug: 2, debt: 2, task: 1, docs: 0 },
      by_priority: { critical: 1, high: 3, medium: 4, low: 2 },
      scan_timestamp: '2026-09-22 12:00:00',
      protocol_version: '3.9.4',
    };

    const mockIssue: Issue = {
      id: 'task--smoke',
      slug: 'smoke',
      protocol: 'along',
      type: 'task',
      status: 'open',
      priority: 'medium',
      title: 'Smoke Test',
      tags: ['test'],
      blocked_by: [],
      related: [],
      body: 'Test body',
      file_path: '.along/ISSUES/task--smoke.md',
      created: '2026-09-22',
      updated: '2026-09-22',
      completed: undefined,
      agent: 'antigravity',
      milestone: undefined,
      parent: undefined,
      superseded_by: undefined,
      duplicate_of: undefined,
    };

    const mockData: FullDashboardData = {
      repo_name: 'along',
      metrics: mockMetrics,
      issues: [mockIssue],
      milestones: [],
      risks: [],
      spikes: [],
      sessions: [],
      decisions: [],
      kb_articles: [],
      graph: {},
      context_text: '',
      issues_board_text: '',
    };

    expect(mockData.repo_name).toBe('along');
    expect(mockData.metrics.protocol_version).toBe('3.9.4');
    expect(mockData.issues).toHaveLength(1);
    expect(mockData.issues[0].slug).toBe('smoke');
  });

  it('validates SearchResultItem type structure', () => {
    const item: SearchResultItem = {
      id: 'kb--intro',
      title: 'Introduction',
      type: 'kb',
      snippet: 'Welcome to Along',
      file_path: 'docs/topic--intro.md',
      score: 1.0,
      tags: ['intro', 'guide'],
    };

    expect(item.type).toBe('kb');
    expect(item.tags).toContain('intro');
  });
});

describe('DashboardApiService Lifecycle', () => {
  it('starts and stops gracefully', () => {
    const service = DashboardApiService.start();
    expect(service).toBeDefined();

    // Verify stop cleans up singleton and EventSource
    DashboardApiService.stop();
  });
});

describe('DOMPurify Markdown Sanitization', () => {
  it('strips malicious script tags from HTML', () => {
    const dangerousHtml = '<p>Normal text</p><script>alert("xss")</script><img src="x" onerror="alert(1)">';
    const clean = DOMPurify.sanitize(dangerousHtml);
    expect(clean).not.toContain('<script>');
    expect(clean).not.toContain('onerror');
    expect(clean).toContain('<p>Normal text</p>');
  });
});
