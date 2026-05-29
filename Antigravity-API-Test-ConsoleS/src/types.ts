/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

export type TestCaseCategory = 'all' | 'positive' | 'missing' | 'unauth';

export type TestExecutionStatus = 'idle' | 'running' | 'success' | 'fail';

export interface TestCase {
  id: string;
  title: string;
  typeText: '【正向】' | '【异常】';
  method: 'POST' | 'GET' | 'PUT' | 'DELETE';
  path: string;
  category: TestCaseCategory;
  status: TestExecutionStatus;
  duration?: number;
  lastResponse?: string;
}

export interface ApiParam {
  name: string;
  type: string;
  required: boolean;
  desc: string;
}

export interface ApiHeader {
  name: string;
  type: string;
  desc: string;
}

export interface ApiEndpoint {
  id: string;
  name: string;
  method: 'POST' | 'GET' | 'PUT' | 'DELETE';
  path: string;
  params: ApiParam[];
  headers: ApiHeader[];
  bodyTemplate: string;
}

export interface ExecutionLog {
  timestamp: string;
  level: 'INFO' | 'WARN' | 'ERROR' | 'SUCCESS';
  message: string;
}

export interface HistoryReport {
  id: string;
  projectName: string;
  environment: string;
  timestamp: string;
  totalCases: number;
  successCount: number;
  failCount: number;
  avgDuration: number;
  passRate: number;
  casesSummary: { id: string; title: string; status: 'success' | 'fail'; duration: number }[];
}
