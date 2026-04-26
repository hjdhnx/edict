export interface AboutMetric {
  label: string;
  value: string;
  hint: string;
}

export interface AboutSection {
  title: string;
  subtitle: string;
  icon: string;
  points: string[];
}

export interface AboutFlowStep {
  role: string;
  phase: string;
  action: string;
  icon: string;
}

export const ABOUT_HERO = {
  title: '三省六部总控台',
  subtitle: '以古制御新技，让 AI Agent 协作有规矩、可追踪、可复盘。',
  description: 'Edict 是本地运行的 AI Agent 工单系统、任务治理层与审计看板。它把模糊指令转成可审议、可执行、可归档的多阶段任务，并通过 AstrBot/OpenClaw 等运行时完成实际工作。',
};

export const ABOUT_METRICS: AboutMetric[] = [
  { label: '治理模型', value: '三省六部', hint: '分拣、起草、审议、派发、执行、复核、回奏' },
  { label: '核心闭环', value: '工单化', hint: '任务 ID、状态、进度、todo、奏折全程留痕' },
  { label: '运行定位', value: '本地优先', hint: '适合本机或可信内网的 Agent 工作台' },
  { label: '产物沉淀', value: '可归档', hint: '报告路径、摘要、正文预览和耗时进入奏折阁' },
];

export const ABOUT_FLOW: AboutFlowStep[] = [
  { role: '太子', phase: '分拣', action: '判断方向与责任链路', icon: '🤴' },
  { role: '中书省', phase: '起草', action: '拆解任务并形成方案', icon: '📜' },
  { role: '门下省', phase: '审议', action: '审核风险，必要时封驳', icon: '🔍' },
  { role: '尚书省', phase: '派发', action: '协调六部执行', icon: '📮' },
  { role: '六部', phase: '执行', action: '完成具体工作并上报', icon: '⚙️' },
  { role: '尚书省', phase: '复核', action: '汇总产物与结果', icon: '🔎' },
  { role: '回奏', phase: '归档', action: '形成奏折与产物入口', icon: '✅' },
];

export const ABOUT_SECTIONS: AboutSection[] = [
  {
    title: '项目定位',
    subtitle: '不是聊天框，也不是古风皮肤',
    icon: '🎯',
    points: [
      '把一次性对话升级为可跟踪的多阶段任务。',
      '通过状态机、角色分工和奏折归档管理 AI 工作过程。',
      '连接 AstrBot/OpenClaw，让外部 Agent 运行时具备工单控制台。',
    ],
  },
  {
    title: '设计理念',
    subtitle: '用制度管理 Agent 不确定性',
    icon: '🏛️',
    points: [
      '规划、审议、执行和复核分离，降低单 Agent 直接动手的风险。',
      '三省六部是治理机制：每个阶段都有责任角色。',
      '既看最终答案，也看过程是否可靠、是否可复盘。',
    ],
  },
  {
    title: '如何使用',
    subtitle: '让值得留痕的任务进入 Edict',
    icon: '🧭',
    points: [
      '下旨时写清楚范围、目标、产物、输出路径和验证要求。',
      '在执行进度看 progress/todo，在省部调度看阻塞与派发状态。',
      '完成后到奏折阁查看摘要、路径、正文预览和耗时。',
    ],
  },
  {
    title: '价值分析',
    subtitle: '把长任务变成可观察资产',
    icon: '📈',
    points: [
      '每个任务有 ID、状态、责任角色、进展和最终报告。',
      '适合代码调研、复杂方案、竞品分析、周报和部署检查。',
      '把 AI 输出从聊天记录沉淀为项目知识资产。',
    ],
  },
  {
    title: '适用场景',
    subtitle: '需要过程和产物的任务更适合',
    icon: '🧩',
    points: [
      '代码库调研、架构评审、功能改造前方案设计。',
      '长周期资料整理、竞品研究、数据报告和团队周报。',
      '需要多 Agent 讨论、审核、复核的复杂判断。',
    ],
  },
  {
    title: '边界说明',
    subtitle: '本地优先，谨慎外放',
    icon: '🛡️',
    points: [
      '当前更适合本机或可信内网，不建议直接公网暴露。',
      '外部 webhook、远程技能、API key 和文件路径需要安全边界。',
      '可靠性依赖 Agent 按协议上报状态、进度和完成产物。',
    ],
  },
];

export const ABOUT_USAGE_TIPS = [
  '如果任务值得有一个 ID、值得看进度、值得保存报告，就适合放进 Edict。',
  '高质量旨意应包含：读取范围、目标问题、输出格式、保存路径、验证方式。',
  '简单问答、临时闲聊、不需要留痕的生成任务，用普通聊天更轻。',
];
