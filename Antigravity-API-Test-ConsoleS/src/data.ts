/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { TestCase, ApiEndpoint, HistoryReport } from './types';

export const INITIAL_TEST_CASES: TestCase[] = [
  {
    id: 'CASE-001',
    title: '创建会话 - 完整参数正常请求',
    typeText: '【正向】',
    method: 'POST',
    path: '/conversation/create',
    category: 'positive',
    status: 'idle',
  },
  {
    id: 'CASE-002',
    title: '创建会话 - 缺失必填参数 [agentId]',
    typeText: '【异常】',
    method: 'POST',
    path: '/conversation/create',
    category: 'missing',
    status: 'idle',
  },
  {
    id: 'CASE-003',
    title: '创建会话 - 鉴权令牌无效',
    typeText: '【异常】',
    method: 'POST',
    path: '/conversation/create',
    category: 'unauth',
    status: 'idle',
  },
  {
    id: 'CASE-004',
    title: '查询会话记录 - 完整参数正常请求',
    typeText: '【正向】',
    method: 'POST',
    path: '/sessions/record/list',
    category: 'positive',
    status: 'idle',
  },
  {
    id: 'CASE-005',
    title: '查询会话记录 - 缺失必填参数 [agentId]',
    typeText: '【异常】',
    method: 'POST',
    path: '/sessions/record/list',
    category: 'missing',
    status: 'idle',
  },
  {
    id: 'CASE-006',
    title: '查询会话记录 - 鉴权令牌无效',
    typeText: '【异常】',
    method: 'POST',
    path: '/sessions/record/list',
    category: 'unauth',
    status: 'idle',
  },
  {
    id: 'CASE-007',
    title: '查询会话详情 - 正常查询已有会话',
    typeText: '【正向】',
    method: 'POST',
    path: '/sessions/record/details',
    category: 'positive',
    status: 'idle',
  },
  {
    id: 'CASE-008',
    title: '查询会话详情 - 查询不存在的会话标识',
    typeText: '【异常】',
    method: 'POST',
    path: '/sessions/record/details',
    category: 'missing',
    status: 'idle',
  },
  {
    id: 'CASE-009',
    title: '修改会话标题 - 完整参数更新请求',
    typeText: '【正向】',
    method: 'POST',
    path: '/sessions/record/update-session-title',
    category: 'positive',
    status: 'idle',
  },
  {
    id: 'CASE-010',
    title: '执行工作流应用（非流式） - AI智能节点调用',
    typeText: '【正向】',
    method: 'POST',
    path: '/workflow/run',
    category: 'positive',
    status: 'idle',
  },
  {
    id: 'CASE-011',
    title: '执行工作流应用（流式） - SSE数据分块推送',
    typeText: '【正向】',
    method: 'POST',
    path: '/workflow/run-stream',
    category: 'positive',
    status: 'idle',
  },
  {
    id: 'CASE-012',
    title: '删除会话 - 循环擦除临时测试会话记录',
    typeText: '【正向】',
    method: 'POST',
    path: '/sessions/record/delete',
    category: 'positive',
    status: 'idle',
  }
];

export const API_ENDPOINTS: ApiEndpoint[] = [
  {
    id: 'API-001',
    name: '创建会话',
    method: 'POST',
    path: '/conversation/create',
    params: [
      { name: 'agentId', type: 'Long', required: true, desc: '智能体id' },
      { name: 'identityId', type: 'Long', required: false, desc: '用户的唯一标识' },
    ],
    headers: [
      { name: 'Content-Type', type: 'string', desc: '固定值 "application/json"' },
      { name: 'Authorization', type: 'string', desc: 'Bearer 格式的令牌' }
    ],
    bodyTemplate: '{\n  "agentId": 24089,\n  "identityId": 10086\n}'
  },
  {
    id: 'API-002',
    name: '查询会话记录',
    method: 'POST',
    path: '/sessions/record/list',
    params: [
      { name: 'agentId', type: 'Long', required: true, desc: '智能体ID' },
      { name: 'pageNum', type: 'Integer', required: false, desc: '页码, 默认1' },
      { name: 'pageSize', type: 'Integer', required: false, desc: '每页条数, 默认10' }
    ],
    headers: [
      { name: 'Content-Type', type: 'string', desc: '固定值 "application/json"' }
    ],
    bodyTemplate: '{\n  "agentId": 24089,\n  "pageNum": 1,\n  "pageSize": 10\n}'
  },
  {
    id: 'API-003',
    name: '查询会话详情',
    method: 'POST',
    path: '/sessions/record/details',
    params: [
      { name: 'sessionId', type: 'String', required: true, desc: '会话唯一标识符' }
    ],
    headers: [
      { name: 'Content-Type', type: 'string', desc: '固定值 "application/json"' }
    ],
    bodyTemplate: '{\n  "sessionId": "sess_894375923"\n}'
  },
  {
    id: 'API-004',
    name: '删除会话',
    method: 'POST',
    path: '/sessions/record/delete',
    params: [
      { name: 'sessionId', type: 'String', required: true, desc: '等待删除的会话标识符' }
    ],
    headers: [
      { name: 'Content-Type', type: 'string', desc: '固定值 "application/json"' }
    ],
    bodyTemplate: '{\n  "sessionId": "sess_894375923"\n}'
  },
  {
    id: 'API-005',
    name: '修改会话标题',
    method: 'POST',
    path: '/sessions/record/update-session-title',
    params: [
      { name: 'sessionId', type: 'String', required: true, desc: '会话ID' },
      { name: 'title', type: 'String', required: true, desc: '新会话展示标题' }
    ],
    headers: [
      { name: 'Content-Type', type: 'string', desc: '固定值 "application/json"' }
    ],
    bodyTemplate: '{\n  "sessionId": "sess_894375923",\n  "title": "关于量子纠缠的探索"\n}'
  },
  {
    id: 'API-006',
    name: '执行工作流应用（非流式响应）',
    method: 'POST',
    path: '/workflow/run',
    params: [
      { name: 'workflowId', type: 'String', required: true, desc: '工作流部署ID' },
      { name: 'inputs', type: 'Map', required: false, desc: '全局节点动态参数' }
    ],
    headers: [
      { name: 'Content-Type', type: 'string', desc: '固定值 "application/json"' }
    ],
    bodyTemplate: '{\n  "workflowId": "wf_neuro_998",\n  "inputs": {\n    "query": "生成一份技术改进建议书"\n  }\n}'
  },
  {
    id: 'API-007',
    name: '执行工作流应用（流式响应）',
    method: 'POST',
    path: '/workflow/run-stream',
    params: [
      { name: 'workflowId', type: 'String', required: true, desc: '工作流部署ID' },
      { name: 'inputs', type: 'Map', required: false, desc: '全局节点配置' }
    ],
    headers: [
      { name: 'Content-Type', type: 'string', desc: '固定值 "application/json"' },
      { name: 'Accept', type: 'string', desc: '必须包含 text/event-stream' }
    ],
    bodyTemplate: '{\n  "workflowId": "wf_neuro_998",\n  "inputs": {\n    "query": "深度剖析分布式高并发架构设计"\n  }\n}'
  },
  {
    id: 'API-008',
    name: '查询异步执行结果',
    method: 'POST',
    path: '/workflow/result',
    params: [
      { name: 'taskId', type: 'String', required: true, desc: '异步工作流执行生成的任务ID' }
    ],
    headers: [
      { name: 'Content-Type', type: 'string', desc: '固定值 "application/json"' }
    ],
    bodyTemplate: '{\n  "taskId": "task_clife_77348957293"\n}'
  },
];

export const INITIAL_HISTORY_REPORTS: HistoryReport[] = [
  {
    id: 'REP-20260526-01',
    projectName: '默认智能体测试项目',
    environment: '测试环境 (itest)',
    timestamp: '2026-05-26 10:45:12',
    totalCases: 12,
    successCount: 11,
    failCount: 1,
    avgDuration: 184,
    passRate: 91.7,
    casesSummary: [
      { id: 'CASE-001', title: '创建会话 - 完整参数正常请求', status: 'success', duration: 156 },
      { id: 'CASE-002', title: '创建会话 - 缺失必填参数 [agentId]', status: 'success', duration: 84 },
      { id: 'CASE-003', title: '创建会话 - 鉴权令牌无效', status: 'success', duration: 112 },
      { id: 'CASE-004', title: '查询会话记录 - 完整参数正常请求', status: 'success', duration: 245 },
      { id: 'CASE-005', title: '查询会话记录 - 缺失必填参数 [agentId]', status: 'fail', duration: 92 },
      { id: 'CASE-006', title: '查询会话记录 - 鉴权令牌无效', status: 'success', duration: 75 },
      { id: 'CASE-007', title: '查询会话详情 - 正常查询已有会话', status: 'success', duration: 128 },
      { id: 'CASE-008', title: '查询会话详情 - 查询不存在的会话标识', status: 'success', duration: 97 },
      { id: 'CASE-009', title: '修改会话标题 - 完整参数更新请求', status: 'success', duration: 198 },
      { id: 'CASE-010', title: '执行工作流应用（非流式） - AI智能节点调用', status: 'success', duration: 340 },
      { id: 'CASE-011', title: '执行工作流应用（流式） - SSE数据分块推送', status: 'success', duration: 520 },
      { id: 'CASE-012', title: '删除会话 - 循环擦除临时测试会话记录', status: 'success', duration: 162 },
    ]
  },
  {
    id: 'REP-20260525-02',
    projectName: '默认智能体测试项目',
    environment: '测试环境 (itest)',
    timestamp: '2026-05-25 16:30:00',
    totalCases: 12,
    successCount: 12,
    failCount: 0,
    avgDuration: 142,
    passRate: 100.0,
    casesSummary: [
      { id: 'CASE-001', title: '创建会话 - 完整参数正常请求', status: 'success', duration: 122 },
      { id: 'CASE-002', title: '创建会话 - 缺失必填参数 [agentId]', status: 'success', duration: 72 },
      { id: 'CASE-003', title: '创建会话 - 鉴权令牌无效', status: 'success', duration: 98 },
      { id: 'CASE-004', title: '查询会话记录 - 完整参数正常请求', status: 'success', duration: 184 },
      { id: 'CASE-005', title: '查询会话记录 - 缺失必填参数 [agentId]', status: 'success', duration: 105 },
      { id: 'CASE-006', title: '查询会话记录 - 鉴权令牌无效', status: 'success', duration: 64 },
      { id: 'CASE-007', title: '查询会话详情 - 正常查询已有会话', status: 'success', duration: 110 },
      { id: 'CASE-008', title: '查询会话详情 - 查询不存在的会话标识', status: 'success', duration: 81 },
      { id: 'CASE-009', title: '修改会话标题 - 完整参数更新请求', status: 'success', duration: 167 },
      { id: 'CASE-010', title: '执行工作流应用（非流式） - AI智能节点调用', status: 'success', duration: 298 },
      { id: 'CASE-011', title: '执行工作流应用（流式） - SSE数据分块推送', status: 'success', duration: 480 },
      { id: 'CASE-012', title: '删除会话 - 循环擦除临时测试会话记录', status: 'success', duration: 140 },
    ]
  }
];
