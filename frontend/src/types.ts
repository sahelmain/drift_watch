export interface User {
  id: string;
  email: string;
  name?: string;
  role: "owner" | "admin" | "member" | "viewer";
  org_id: string;
  created_at: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  plan: "free" | "pro" | "enterprise";
  created_at: string;
}

export interface Suite {
  id: string;
  name: string;
  description?: string;
  yaml_content?: string;
  schedule_cron?: string;
  is_active: boolean;
  org_id: string;
  created_at: string;
  updated_at: string;
}

export interface TestRun {
  id: string;
  suite_id: string;
  suite_name?: string;
  status: "pending" | "running" | "passed" | "failed" | "error";
  trigger: "manual" | "schedule" | "ci" | "api";
  pass_rate?: number;
  total_tests: number;
  passed_tests: number;
  failed_tests: number;
  duration_ms?: number;
  started_at?: string;
  completed_at?: string;
  created_at?: string;
  results?: TestResult[];
}

export interface TestResult {
  id: string;
  run_id: string;
  test_name: string;
  model: string;
  passed: boolean;
  output: string;
  expected?: string;
  latency_ms: number;
  tokens_used: number;
  cost?: number;
  assertions: AssertionResult[];
}

export interface AssertionResult {
  name: string;
  type: string;
  passed: boolean;
  expected?: string;
  actual?: string;
  message?: string;
}

export interface DriftScore {
  date: string;
  pass_rate: number;
  drift_score: number;
  run_id: string;
  total_tests: number;
  failed_tests: number;
}

export interface AlertConfig {
  id: string;
  channel: "slack" | "email" | "pagerduty" | "jira";
  destination: string;
  threshold_metric: string;
  threshold_value: number;
  suite_id?: string;
  org_id: string;
  enabled: boolean;
  created_at: string;
}

export interface AlertEvent {
  id: string;
  alert_id: string;
  channel: string;
  destination: string;
  metric_value: number;
  threshold: number;
  status: "sent" | "failed";
  created_at: string;
}

export interface Policy {
  id: string;
  name: string;
  metric: string;
  operator: "lt" | "gt" | "eq" | "lte" | "gte";
  threshold: number;
  action: "block" | "warn" | "notify";
  enabled: boolean;
  created_at: string;
}

export interface AuditEvent {
  id: string;
  action: string;
  user_id: string;
  user_email?: string;
  resource_type: string;
  resource_id: string;
  details?: Record<string, unknown>;
  created_at: string;
  timestamp?: string;
}

export interface ApiKey {
  id: string;
  prefix: string;
  name: string;
  created_at: string;
  last_used_at?: string;
}

export interface OrgSettings {
  org: Organization;
  members: User[];
  api_keys: ApiKey[];
  usage: {
    runs_this_month: number;
    suites_count: number;
    plan_limit: number;
  };
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}
