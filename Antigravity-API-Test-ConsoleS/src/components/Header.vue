<script setup lang="ts">
import { ref } from 'vue';
import { Zap, Server, Shield, Globe, Plus, Cpu, HelpCircle, ExternalLink, X, Edit2, Trash2 } from 'lucide-vue-next';

interface Props {
  projects: any[];
  envs: any[];
  activeProjectId: number | null;
  activeEnvId: number | null;
  domainUrl: string;
  token: string;
}

const props = defineProps<Props>();
const emit = defineEmits([
  'update:activeProjectId',
  'update:activeEnvId',
  'update:domainUrl',
  'update:token',
  'reload-projects',
  'reload-envs'
]);

// Popover states
const showDomainEdit = ref(false);
const showTokenHelp = ref(false);

// CRUD Dialog states
const showProjectModal = ref(false);
const showEnvModal = ref(false);

// Project Edit Form states
const showProjectForm = ref(false);
const projectFormMode = ref<'create' | 'edit'>('create');
const currentEditProjectId = ref<number | null>(null);
const projectForm = ref({
  name: '',
  description: '',
  md_path: ''
});

// Env Edit Form states
const showEnvForm = ref(false);
const envFormMode = ref<'create' | 'edit'>('create');
const currentEditEnvId = ref<number | null>(null);
const envForm = ref({
  name: '',
  base_url: ''
});

// Project CRUD Operations
function openCreateProject() {
  projectFormMode.value = 'create';
  projectForm.value = { name: '', description: '', md_path: '' };
  showProjectForm.value = true;
}

function openEditProject(proj: any) {
  projectFormMode.value = 'edit';
  currentEditProjectId.value = proj.id;
  projectForm.value = {
    name: proj.name,
    description: proj.description || '',
    md_path: proj.md_path
  };
  showProjectForm.value = true;
}

async function saveProject() {
  if (!projectForm.value.name.trim() || !projectForm.value.md_path.trim()) {
    alert('请填写项目名称和绝对文档路径！');
    return;
  }
  
  try {
    const url = projectFormMode.value === 'create' 
      ? '/api/projects' 
      : `/api/projects/${currentEditProjectId.value}`;
    const method = projectFormMode.value === 'create' ? 'POST' : 'PUT';
    
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(projectForm.value)
    });
    
    const json = await res.json();
    if (res.ok && json.success) {
      showProjectForm.value = false;
      emit('reload-projects', json.data?.id);
    } else {
      alert(`保存失败: ${json.detail || '未知的后端校验错误'}`);
    }
  } catch (err: any) {
    alert(`通信异常: ${err.message}`);
  }
}

async function deleteProject(id: number) {
  if (!confirm('确定要删除该项目吗？这将会清空项目下所有的历史报告数据！')) return;
  try {
    const res = await fetch(`/api/projects/${id}`, { method: 'DELETE' });
    const json = await res.json();
    if (json.success) {
      emit('reload-projects');
    } else {
      alert(`删除失败: ${json.detail}`);
    }
  } catch (err: any) {
    alert(`通信异常: ${err.message}`);
  }
}

// Env CRUD Operations
function openCreateEnv() {
  envFormMode.value = 'create';
  envForm.value = { name: '', base_url: '' };
  showEnvForm.value = true;
}

function openEditEnv(env: any) {
  envFormMode.value = 'edit';
  currentEditEnvId.value = env.id;
  envForm.value = {
    name: env.name,
    base_url: env.base_url
  };
  showEnvForm.value = true;
}

async function saveEnv() {
  if (!envForm.value.name.trim() || !envForm.value.base_url.trim()) {
    alert('请填写环境名称和基地址！');
    return;
  }
  
  try {
    const url = envFormMode.value === 'create' 
      ? '/api/envs' 
      : `/api/envs/${currentEditEnvId.value}`;
    const method = envFormMode.value === 'create' ? 'POST' : 'PUT';
    
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(envForm.value)
    });
    
    const json = await res.json();
    if (res.ok && json.success) {
      showEnvForm.value = false;
      emit('reload-envs', json.data?.id);
    } else {
      alert(`保存失败: ${json.detail}`);
    }
  } catch (err: any) {
    alert(`通信异常: ${err.message}`);
  }
}

async function deleteEnv(id: number) {
  if (!confirm('确定要删除该测试环境域名吗？')) return;
  try {
    const res = await fetch(`/api/envs/${id}`, { method: 'DELETE' });
    const json = await res.json();
    if (json.success) {
      emit('reload-envs');
    } else {
      alert(`删除失败: ${json.detail}`);
    }
  } catch (err: any) {
    alert(`通信异常: ${err.message}`);
  }
}
</script>

<template>
  <header class="relative w-full bg-white border-b border-rose-50/10 shadow-sm ring-1 ring-slate-100 px-6 py-4 rounded-2xl mb-6">
    <!-- Visual Accent top ribbon -->
    <div class="absolute top-0 left-0 right-0 h-[3px] bg-gradient-to-r from-violet-500 via-pink-500 to-indigo-500 rounded-t-2xl" />

    <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
      <!-- Logo & Platform Info -->
      <div class="flex items-center gap-3">
        <div class="flex items-center justify-center p-2 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-xl shadow-md text-white animate-pulse-subtle shrink-0">
          <Zap class="w-5 h-5" />
        </div>
        <div>
          <div class="flex flex-wrap items-center gap-2">
            <h1 class="text-lg sm:text-xl font-black tracking-tight bg-gradient-to-r from-slate-900 via-violet-700 to-indigo-600 bg-clip-text text-transparent">
              Antigravity TEST CONSOLE
            </h1>
            <span class="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono font-bold text-violet-600 bg-violet-50 border border-violet-100 rounded-full">
              <Cpu class="w-2.5 h-2.5" />
              INTELLIGENT AGENT v3.1
            </span>
          </div>
          <p class="text-[10px] sm:text-xs text-slate-400 mt-0.5 font-medium">
            大模型多项目接口自动化测试与环境配置分析平台
          </p>
        </div>
      </div>

      <!-- Global Controls Panel -->
      <div class="flex flex-wrap items-center gap-3 text-xs">
        <!-- Project Switcher -->
        <div class="flex items-center gap-1.5 bg-slate-50 border border-slate-200/80 px-2.5 py-1.5 rounded-lg focus-within:ring-2 focus-within:ring-violet-500/20 focus-within:border-violet-500 transition-all">
          <span class="text-slate-400 font-medium">测试项目:</span>
          <select
            :value="activeProjectId"
            @change="emit('update:activeProjectId', Number(($event.target as HTMLSelectElement).value))"
            class="bg-transparent text-slate-700 font-semibold focus:outline-none cursor-pointer"
          >
            <option v-for="p in projects" :key="p.id" :value="p.id">
              {{ p.name }}
            </option>
            <option v-if="projects.length === 0" disabled value="">暂无项目，请新建</option>
          </select>
          <button
            @click="showProjectModal = true"
            title="管理项目"
            class="p-0.5 hover:bg-slate-200 rounded-sm text-slate-500 transition-colors cursor-pointer"
          >
            <Plus class="w-3.5 h-3.5" />
          </button>
        </div>

        <!-- Environment Domain Toggle -->
        <div class="flex items-center gap-1.5 bg-slate-50 border border-slate-200/80 px-2.5 py-1.5 rounded-lg focus-within:ring-2 focus-within:ring-violet-500/20 focus-within:border-violet-500 transition-all">
          <span class="text-slate-400 font-medium">测试环境:</span>
          <select
            :value="activeEnvId"
            @change="emit('update:activeEnvId', Number(($event.target as HTMLSelectElement).value))"
            class="bg-transparent text-slate-700 font-semibold focus:outline-none cursor-pointer"
          >
            <option v-for="env in envs" :key="env.id" :value="env.id">
              {{ env.name }}
            </option>
            <option v-if="envs.length === 0" disabled value="">暂无环境，请新建</option>
          </select>
          <button
            @click="showEnvModal = true"
            title="管理环境"
            class="p-0.5 hover:bg-slate-200 rounded-sm text-slate-500 transition-colors cursor-pointer"
          >
            <Plus class="w-3.5 h-3.5" />
          </button>
        </div>

        <!-- Custom URL Popover Toggle -->
        <div class="relative">
          <button
            @click="showDomainEdit = !showDomainEdit"
            class="flex items-center gap-1.5 bg-violet-50 text-violet-700 hover:bg-violet-100 hover:text-violet-800 border border-violet-100 px-3 py-1.5 rounded-lg font-medium cursor-pointer transition-colors"
          >
            <Globe class="w-3.5 h-3.5 text-violet-500" />
            <span>环境域名</span>
          </button>

          <!-- Dropdown Popover (Domain edit) -->
          <div v-if="showDomainEdit" class="absolute right-0 mt-2 w-72 bg-white border border-slate-200 rounded-xl shadow-xl z-50 p-4">
            <!-- Backdrop layer to close -->
            <div class="fixed inset-0 z-[-1]" @click="showDomainEdit = false" />
            
            <div class="flex items-center justify-between mb-2">
              <span class="font-semibold text-slate-700">配置环境域名</span>
              <Server class="w-3.5 h-3.5 text-slate-400" />
            </div>
            <input
              type="text"
              :value="domainUrl"
              @input="emit('update:domainUrl', ($event.target as HTMLInputElement).value)"
              class="w-full text-xs font-mono p-2 border border-slate-200 rounded-md focus:ring-2 focus:ring-violet-500 focus:border-violet-500 outline-none"
              placeholder="https://example.com/api"
            />
            <div class="flex justify-between items-center mt-3 text-[10px] text-slate-400">
              <span class="flex items-center gap-1">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                当前网关已联通
              </span>
              <a
                :href="domainUrl"
                target="_blank"
                rel="noreferrer"
                class="text-violet-600 hover:underline flex items-center gap-0.5"
              >
                测试连接 <ExternalLink class="w-2.5 h-2.5" />
              </a>
            </div>
          </div>
        </div>

        <!-- Homingtoken input -->
        <div class="relative flex items-center gap-2">
          <div class="flex items-center bg-slate-50 w-52 sm:w-60 border border-slate-200 rounded-lg overflow-hidden focus-within:ring-2 focus-within:ring-violet-500/20 focus-within:border-violet-500 transition-all">
            <div class="bg-slate-100 border-r border-slate-200 px-2 py-1.5 flex items-center gap-1 text-slate-500 shrink-0 select-none">
              <Shield class="w-3.5 h-3.5" />
              <span class="font-medium text-[10px] uppercase">Token</span>
            </div>
            <input
              type="password"
              :value="token"
              @input="emit('update:token', ($event.target as HTMLInputElement).value)"
              placeholder="请输入 homingtoken"
              class="w-full bg-transparent px-2.5 py-1.5 text-xs text-slate-700 font-mono focus:outline-none"
            />
          </div>
          <button
            @click="showTokenHelp = !showTokenHelp"
            class="p-1 text-slate-400 hover:text-slate-600 transition-colors cursor-pointer"
          >
            <HelpCircle class="w-4 h-4" />
          </button>

          <!-- Dropdown Popover (Token help) -->
          <div v-if="showTokenHelp" class="absolute right-0 top-10 w-64 bg-slate-800 text-slate-200 border border-slate-700 rounded-lg shadow-xl z-50 p-3 text-[11px]">
            <div class="fixed inset-0 z-[-1]" @click="showTokenHelp = false" />
            <p class="font-semibold text-slate-100 mb-1">什么是 HomingToken?</p>
            <p class="leading-relaxed">
              用于对后端 Agent 网关服务器交互执行的接口进行安全身份鉴权的令牌。未提供该令牌可能会降低测试评测限制。
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- MODAL 1: Project CRUD Management -->
    <div v-if="showProjectModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
      <div class="bg-white w-full max-w-4xl rounded-2xl shadow-2xl border border-slate-100 flex flex-col max-h-[85vh] overflow-hidden">
        <div class="p-5 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <h3 class="text-sm font-bold text-slate-800">📁 测试项目配置管理</h3>
          <button @click="showProjectModal = false" class="p-1 text-slate-400 hover:text-slate-650 cursor-pointer">
            <X class="w-4.5 h-4.5" />
          </button>
        </div>
        <div class="p-6 overflow-y-auto space-y-4 flex-1">
          <div class="flex justify-between items-center text-xs">
            <span class="text-slate-500">在这里创建和配置不同的测试项目，每个项目可绑定专属的 md 文档。</span>
            <button @click="openCreateProject" class="px-3 py-1.5 bg-violet-600 hover:bg-violet-700 text-white rounded-lg font-semibold flex items-center gap-1 cursor-pointer">
              <Plus class="w-3.5 h-3.5" /> 新建测试项目
            </button>
          </div>

          <!-- Table of Projects -->
          <div class="border border-slate-200 rounded-xl overflow-hidden shadow-xs">
            <table class="w-full text-left border-collapse text-xs text-slate-600">
              <thead>
                <tr class="bg-slate-50 border-b border-slate-200 text-slate-500 font-bold">
                  <th class="p-3 pl-4 w-12 text-center">ID</th>
                  <th class="p-3 w-44">项目名称</th>
                  <th class="p-3">文档绝对路径</th>
                  <th class="p-3 w-40">项目描述</th>
                  <th class="p-3 pr-4 w-28 text-center">操作</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100">
                <tr v-for="proj in projects" :key="proj.id" class="hover:bg-slate-50/50">
                  <td class="p-3 pl-4 font-mono font-semibold text-center">{{ proj.id }}</td>
                  <td class="p-3 font-bold text-slate-800">{{ proj.name }}</td>
                  <td class="p-3 font-mono text-slate-500 break-all select-all">{{ proj.md_path }}</td>
                  <td class="p-3 text-slate-400 truncate max-w-[150px]">{{ proj.description || '无描述' }}</td>
                  <td class="p-3 pr-4 text-center space-x-2.5">
                    <button @click="openEditProject(proj)" class="text-violet-600 hover:text-violet-800 font-semibold cursor-pointer inline-flex items-center gap-0.5">
                      <Edit2 class="w-3 h-3" /> 编辑
                    </button>
                    <button @click="deleteProject(proj.id)" class="text-rose-600 hover:text-rose-800 font-semibold cursor-pointer inline-flex items-center gap-0.5">
                      <Trash2 class="w-3 h-3" /> 删除
                    </button>
                  </td>
                </tr>
                <tr v-if="projects.length === 0">
                  <td colspan="5" class="p-8 text-center text-slate-400 font-medium">暂无测试项目记录，请立即点击上方按钮新建！</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Project Form Dialog (nested layout) -->
          <div v-if="showProjectForm" class="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-4">
            <h4 class="font-bold text-slate-800 text-xs flex items-center justify-between">
              <span>{{ projectFormMode === 'create' ? '✨ 新建测试项目' : '✏️ 编辑测试项目' }}</span>
              <button @click="showProjectForm = false" class="text-slate-400 hover:text-slate-600 cursor-pointer"><X class="w-4 h-4" /></button>
            </h4>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div class="space-y-1">
                <label class="font-semibold text-slate-600 block">项目名称:</label>
                <input v-model="projectForm.name" type="text" placeholder="例如：大模型智能协同脑" class="w-full p-2 border border-slate-200 bg-white rounded-lg focus:ring-1 focus:ring-violet-500 focus:border-violet-500 outline-none" />
              </div>
              <div class="space-y-1">
                <label class="font-semibold text-slate-600 block">接口文档绝对路径 (.md):</label>
                <input v-model="projectForm.md_path" type="text" placeholder="C:\CaseAi\Apicase\接口清单.md" class="w-full p-2 border border-slate-200 bg-white rounded-lg focus:ring-1 focus:ring-violet-500 focus:border-violet-500 outline-none font-mono" />
              </div>
              <div class="space-y-1 md:col-span-2">
                <label class="font-semibold text-slate-600 block">项目描述 (可选):</label>
                <textarea v-model="projectForm.description" rows="2" placeholder="请输入项目的核心测试用途或其它说明备注..." class="w-full p-2 border border-slate-200 bg-white rounded-lg focus:ring-1 focus:ring-violet-500 focus:border-violet-500 outline-none resize-none"></textarea>
              </div>
            </div>
            <div class="flex justify-end gap-2 text-xs">
              <button @click="showProjectForm = false" class="px-3 py-1.5 bg-white border border-slate-200 text-slate-700 rounded-lg hover:bg-slate-100 cursor-pointer">取消</button>
              <button @click="saveProject" class="px-4 py-1.5 bg-violet-600 text-white rounded-lg hover:bg-violet-750 cursor-pointer font-semibold">保存</button>
            </div>
          </div>
        </div>
        
        <div class="p-4 border-t border-slate-100 bg-slate-50 flex justify-end">
          <button @click="showProjectModal = false" class="px-4 py-1.5 bg-white border border-slate-200 text-slate-700 rounded-lg hover:bg-slate-100 cursor-pointer text-xs font-semibold">确定 / 关闭</button>
        </div>
      </div>
    </div>

    <!-- MODAL 2: Environments CRUD Management -->
    <div v-if="showEnvModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
      <div class="bg-white w-full max-w-3xl rounded-2xl shadow-2xl border border-slate-100 flex flex-col max-h-[85vh] overflow-hidden">
        <div class="p-5 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <h3 class="text-sm font-bold text-slate-800">🌐 测试环境域名管理</h3>
          <button @click="showEnvModal = false" class="p-1 text-slate-400 hover:text-slate-600 cursor-pointer">
            <X class="w-4.5 h-4.5" />
          </button>
        </div>
        
        <div class="p-6 overflow-y-auto space-y-4 flex-1 text-xs">
          <div class="flex justify-between items-center">
            <span class="text-slate-500">在此处无限制地拓展您需要测试的基地址（环境域名），运行测试时可以一键切换。</span>
            <button @click="openCreateEnv" class="px-3 py-1.5 bg-violet-600 hover:bg-violet-700 text-white rounded-lg font-semibold flex items-center gap-1 cursor-pointer">
              <Plus class="w-3.5 h-3.5" /> 新增环境域名
            </button>
          </div>

          <!-- Table of Envs -->
          <div class="border border-slate-200 rounded-xl overflow-hidden shadow-xs">
            <table class="w-full text-left border-collapse text-xs text-slate-600">
              <thead>
                <tr class="bg-slate-50 border-b border-slate-200 text-slate-500 font-bold">
                  <th class="p-3 pl-4 w-12 text-center">ID</th>
                  <th class="p-3 w-40">环境名称</th>
                  <th class="p-3">域名基地址 (Base URL)</th>
                  <th class="p-3 pr-4 w-28 text-center">操作</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100">
                <tr v-for="env in envs" :key="env.id" class="hover:bg-slate-50/50">
                  <td class="p-3 pl-4 font-mono font-semibold text-center">{{ env.id }}</td>
                  <td class="p-3 font-bold text-slate-800">{{ env.name }}</td>
                  <td class="p-3 font-mono text-slate-500 break-all select-all">{{ env.base_url }}</td>
                  <td class="p-3 pr-4 text-center space-x-2.5">
                    <button @click="openEditEnv(env)" class="text-violet-600 hover:text-violet-800 font-semibold cursor-pointer inline-flex items-center gap-0.5">
                      <Edit2 class="w-3 h-3" /> 编辑
                    </button>
                    <button @click="deleteEnv(env.id)" class="text-rose-600 hover:text-rose-800 font-semibold cursor-pointer inline-flex items-center gap-0.5">
                      <Trash2 class="w-3 h-3" /> 删除
                    </button>
                  </td>
                </tr>
                <tr v-if="envs.length === 0">
                  <td colspan="4" class="p-8 text-center text-slate-400 font-medium">暂无环境域名配置，请立即点击上方按钮新增！</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Env Form Dialog -->
          <div v-if="showEnvForm" class="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-4">
            <h4 class="font-bold text-slate-800 text-xs flex items-center justify-between">
              <span>{{ envFormMode === 'create' ? '✨ 新增环境域名' : '✏️ 编辑环境域名' }}</span>
              <button @click="showEnvForm = false" class="text-slate-400 hover:text-slate-600 cursor-pointer"><X class="w-4 h-4" /></button>
            </h4>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div class="space-y-1">
                <label class="font-semibold text-slate-600 block">环境名称:</label>
                <input v-model="envForm.name" type="text" placeholder="例如：预发测试环境" class="w-full p-2 border border-slate-200 bg-white rounded-lg focus:ring-1 focus:ring-violet-500 focus:border-violet-500 outline-none" />
              </div>
              <div class="space-y-1">
                <label class="font-semibold text-slate-600 block">域名基地址 (Base URL):</label>
                <input v-model="envForm.base_url" type="text" placeholder="https://pre.clife.net/agentpaas" class="w-full p-2 border border-slate-200 bg-white rounded-lg focus:ring-1 focus:ring-violet-500 focus:border-violet-500 outline-none font-mono" />
              </div>
            </div>
            <div class="flex justify-end gap-2 text-xs">
              <button @click="showEnvForm = false" class="px-3 py-1.5 bg-white border border-slate-200 text-slate-700 rounded-lg hover:bg-slate-100 cursor-pointer">取消</button>
              <button @click="saveEnv" class="px-4 py-1.5 bg-violet-600 text-white rounded-lg hover:bg-violet-750 cursor-pointer font-semibold">保存</button>
            </div>
          </div>
        </div>
        
        <div class="p-4 border-t border-slate-100 bg-slate-50 flex justify-end">
          <button @click="showEnvModal = false" class="px-4 py-1.5 bg-white border border-slate-200 text-slate-700 rounded-lg hover:bg-slate-100 cursor-pointer text-xs font-semibold">确定 / 关闭</button>
        </div>
      </div>
    </div>
  </header>
</template>

<style scoped>
.animate-pulse-subtle {
  animation: pulse-subtle 3s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse-subtle {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: .92;
    transform: scale(0.98);
  }
}
</style>
