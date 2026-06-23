/* ============================================================
   AgentOS — Mock Data
   ============================================================ */

export const INIT_TASKS = [
  { id:'T001', name:'文档智能解析与摘要', agent:'DocAgent', priority:'high', status:'running', progress:72, created:'06-22 18:30', desc:'解析48页PDF报告，提取财务数据、表格和图表信息，生成结构化JSON和Excel输出。', skills:['PDF解析器','摘要生成'] },
  { id:'T002', name:'代码安全漏洞扫描', agent:'CodeAgent', priority:'high', status:'running', progress:45, created:'06-22 17:50', desc:'对Node.js API层进行全量安全扫描，检测注入、XSS、CSRF等漏洞类型。', skills:['代码审查','异常检测'] },
  { id:'T003', name:'客户意图分类模型训练', agent:'MLAgent', priority:'medium', status:'pending', progress:0, created:'06-22 17:20', desc:'使用5000条标注对话数据训练意图分类模型，目标准确率>92%。', skills:['情感分析','知识图谱'] },
  { id:'T004', name:'API文档自动生成', agent:'DocAgent', priority:'low', status:'done', progress:100, created:'06-22 16:40', desc:'扫描代码注释和接口定义，自动生成OpenAPI 3.0规范的文档。', skills:['PDF解析器','代码生成'] },
  { id:'T005', name:'竞品情报抓取分析', agent:'ResearchAgent', priority:'medium', status:'running', progress:88, created:'06-22 16:10', desc:'抓取15个竞品网站的产品功能矩阵和定价信息，输出对比分析报告。', skills:['Web爬取','语义搜索'] },
  { id:'T006', name:'邮件批量回复处理', agent:'CommAgent', priority:'low', status:'done', progress:100, created:'06-22 15:30', desc:'根据上下文和规则库自动回复客户邮件，每日处理量约200封。', skills:['翻译引擎','摘要生成'] },
  { id:'T007', name:'数据库查询优化建议', agent:'DBAgent', priority:'high', status:'failed', progress:33, created:'06-22 14:50', desc:'分析慢查询日志，生成SQL优化建议和索引方案。', skills:['SQL生成','知识图谱'] },
  { id:'T008', name:'日志异常检测与告警', agent:'MonitorAgent', priority:'medium', status:'running', progress:61, created:'06-22 14:10', desc:'实时分析应用日志流，检测异常模式并触发分级告警通知。', skills:['异常检测','Web爬取'] },
  { id:'T009', name:'用户行为分析报告', agent:'AnalyticsAgent', priority:'medium', status:'pending', progress:0, created:'06-22 13:40', desc:'分析近30天用户行为轨迹，输出留存率、转化漏斗和热力图数据。', skills:['图像理解','语义搜索'] },
  { id:'T010', name:'图片内容理解标注', agent:'VisionAgent', priority:'low', status:'done', progress:100, created:'06-22 12:50', desc:'批量标注1200张商品图片，识别品类、属性、瑕疵等32个维度。', skills:['图像理解','代码生成'] },
  { id:'T011', name:'合同条款风险识别', agent:'LegalAgent', priority:'high', status:'pending', progress:0, created:'06-22 12:20', desc:'自动审阅合同文档，识别风险条款和不合理约定。', skills:['PDF解析器','摘要生成'] },
  { id:'T012', name:'多语言翻译质量评估', agent:'LangAgent', priority:'low', status:'running', progress:29, created:'06-22 11:40', desc:'评估机器翻译引擎在中英日韩4语言对的BLEU/COMET评分。', skills:['翻译引擎','摘要生成'] },
];

export const INIT_AGENTS = [
  { id:'A001', name:'DocAgent', type:'文档处理', status:'online', model:'GPT-4o', tasks:3, cpu:'28%', mem:'1.2GB', skills:['PDF解析','摘要生成','OCR识别'], color:'blue', uptime:'12h 34m', desc:'专业文档处理Agent，擅长PDF解析、数据提取和格式化输出。' },
  { id:'A002', name:'CodeAgent', type:'代码分析', status:'online', model:'Claude-3.5', tasks:2, cpu:'62%', mem:'2.8GB', skills:['代码审查','漏洞检测','重构建议'], color:'green', uptime:'8h 12m', desc:'全栈代码分析Agent，覆盖安全审计、性能诊断和最佳实践建议。' },
  { id:'A003', name:'MLAgent', type:'机器学习', status:'online', model:'Gemini-1.5', tasks:1, cpu:'85%', mem:'6.4GB', skills:['模型训练','数据预处理','评估报告'], color:'purple', uptime:'3h 55m', desc:'机器学习工作台，支持数据清洗、特征工程、模型训练和评估全流程。' },
  { id:'A004', name:'ResearchAgent', type:'信息检索', status:'online', model:'GPT-4o', tasks:2, cpu:'41%', mem:'1.8GB', skills:['Web搜索','数据抓取','情报分析'], color:'amber', uptime:'24h 00m', desc:'智能信息检索Agent，支持网络爬取、多维搜索和结构化情报分析。' },
  { id:'A005', name:'MonitorAgent', type:'系统监控', status:'online', model:'Claude-3', tasks:1, cpu:'12%', mem:'0.8GB', skills:['日志分析','告警推送','性能追踪'], color:'coral', uptime:'72h 18m', desc:'7×24系统监控，实时检测异常指标并触发分级告警。' },
  { id:'A006', name:'VisionAgent', type:'视觉理解', status:'idle', model:'GPT-4V', tasks:0, cpu:'0%', mem:'3.2GB', skills:['图像识别','内容标注','OCR'], color:'blue', uptime:'6h 05m', desc:'多模态视觉理解Agent，支持图像分类、目标检测和场景描述。' },
  { id:'A007', name:'CommAgent', type:'通信协作', status:'idle', model:'Claude-3', tasks:0, cpu:'2%', mem:'0.6GB', skills:['邮件处理','日程管理','消息路由'], color:'green', uptime:'18h 42m', desc:'智能通信助手，自动处理邮件、安排日程和跨平台消息同步。' },
  { id:'A008', name:'DBAgent', type:'数据库', status:'offline', model:'GPT-4', tasks:0, cpu:'—', mem:'—', skills:['SQL优化','Schema设计','数据迁移'], color:'purple', uptime:'离线', desc:'数据库管理Agent，处理SQL优化、索引设计和数据迁移任务。' },
];

export const INIT_SKILLS = [
  { id:'S001', name:'PDF 解析器', category:'文档', desc:'支持复杂PDF提取，含表格、图表、公式识别，精度98%+', version:'2.1.3', usage:847, icon:'📄', color:'blue', type:'Python函数', author:'DocAgent团队' },
  { id:'S002', name:'代码审查', category:'开发', desc:'多语言代码质量分析，覆盖安全、性能、规范三维度', version:'1.5.0', usage:623, icon:'🔍', color:'green', type:'HTTP API', author:'CodeAgent团队' },
  { id:'S003', name:'语义搜索', category:'搜索', desc:'基于向量嵌入的语义相似度检索，支持跨语言搜索', version:'3.0.1', usage:1204, icon:'🔎', color:'cyan', type:'MCP协议', author:'ResearchAgent团队' },
  { id:'S004', name:'图像理解', category:'视觉', desc:'目标检测、场景理解、OCR文字识别一体化能力', version:'2.3.0', usage:389, icon:'🖼️', color:'purple', type:'Python函数', author:'VisionAgent团队' },
  { id:'S005', name:'情感分析', category:'NLP', desc:'细粒度情感极性判断，支持多语言及领域自适应', version:'1.8.2', usage:756, icon:'💬', color:'amber', type:'HTTP API', author:'MLAgent团队' },
  { id:'S006', name:'Web 爬取', category:'搜索', desc:'反反爬绕过、JS渲染、结构化数据提取一站式方案', version:'2.0.4', usage:512, icon:'🕷️', color:'coral', type:'Python函数', author:'ResearchAgent团队' },
  { id:'S007', name:'SQL 生成', category:'数据库', desc:'自然语言转SQL，支持复杂JOIN和子查询，正确率94%', version:'1.2.1', usage:1089, icon:'🗃️', color:'green', type:'HTTP API', author:'DBAgent团队' },
  { id:'S008', name:'摘要生成', category:'NLP', desc:'长文档智能摘要，支持章节摘要和全文摘要两种模式', version:'2.4.0', usage:934, icon:'📝', color:'blue', type:'Python函数', author:'DocAgent团队' },
  { id:'S009', name:'翻译引擎', category:'NLP', desc:'支持120+语言对互译，保留格式和专业术语准确性', version:'3.1.2', usage:678, icon:'🌐', color:'purple', type:'HTTP API', author:'LangAgent团队' },
  { id:'S010', name:'异常检测', category:'监控', desc:'时序数据异常识别，支持实时流和批量历史数据分析', version:'1.6.0', usage:423, icon:'⚡', color:'red', type:'Python函数', author:'MonitorAgent团队' },
  { id:'S011', name:'代码生成', category:'开发', desc:'基于需求描述自动生成代码片段，支持25种编程语言', version:'2.2.3', usage:2103, icon:'⚙️', color:'green', type:'MCP协议', author:'CodeAgent团队' },
  { id:'S012', name:'知识图谱', category:'数据库', desc:'实体关系抽取与图谱构建，支持增量更新', version:'1.0.5', usage:267, icon:'🕸️', color:'amber', type:'Python函数', author:'DBAgent团队' },
];

export const INIT_MEMORY = [
  { id:'M001', type:'fact', content:'用户偏好使用Claude-3.5模型处理代码相关任务，GPT-4o用于文档分析', agent:'System', time:'06-22 20:31', tags:['用户偏好','模型配置'] },
  { id:'M002', type:'conversation', content:'用户询问了关于多Agent协同时任务分配策略的问题，讨论了基于能力匹配和负载均衡的两种方案', agent:'DocAgent', time:'06-22 20:15', tags:['任务分配','协同策略'] },
  { id:'M003', type:'skill', content:'PDF解析技能v2.1.3在处理带水印文档时需要先进行预处理，直接解析会导致字符乱码', agent:'DocAgent', time:'06-22 19:48', tags:['PDF解析','边缘案例'] },
  { id:'M004', type:'context', content:'当前项目代码库使用TypeScript 5.x + React 18，测试框架为Vitest，部署在Kubernetes集群', agent:'CodeAgent', time:'06-22 19:20', tags:['项目上下文','技术栈'] },
  { id:'M005', type:'fact', content:'数据库主库位于us-east-1，读副本在eu-west-1和ap-southeast-1，写操作延迟约5-8ms', agent:'DBAgent', time:'06-22 18:55', tags:['数据库','基础设施'] },
  { id:'M006', type:'conversation', content:'CodeAgent在安全扫描中发现3个中危漏洞，均涉及SQL注入风险，已生成修复建议并通知开发团队', agent:'CodeAgent', time:'06-22 18:30', tags:['安全','漏洞'] },
  { id:'M007', type:'skill', content:'语义搜索在跨语言检索中，中英混合查询效果最佳，纯英文查询比中文略高5%精度', agent:'ResearchAgent', time:'06-22 17:45', tags:['语义搜索','多语言'] },
  { id:'M008', type:'context', content:'本次会话重点：构建多Agent前端管理界面，需要科技风UI设计，响应式布局', agent:'System', time:'06-22 20:43', tags:['当前任务','UI设计'] },
];

export const INIT_SESSIONS = [
  { id:'SS001', name:'文档处理工作流调试', agent:'DocAgent', preview:'正在分析PDF结构，发现第3页存在复杂表格...', time:'2分钟前', messages:[
    { role:'user', content:'帮我解析这个PDF报告，提取所有财务数据', time:'20:35' },
    { role:'agent', content:'收到！正在分析PDF结构...\n\n检测到文档共48页，包含15个数据表格和32个图表。\n\n当前进度：\n✅ 文本提取完成\n✅ 表格识别完成\n🔄 数据结构化处理中...', time:'20:35' },
    { role:'user', content:'重点提取第8-12页的损益表数据', time:'20:37' },
    { role:'agent', content:'已定位到第8-12页损益表区域：\n\n📊 营业收入：¥23.8亿（同比+18.3%）\n📊 营业成本：¥15.2亿\n📊 毛利润：¥8.6亿（毛利率36.1%）\n📊 净利润：¥3.4亿（净利率14.3%）', time:'20:38' },
  ]},
  { id:'SS002', name:'代码安全审计', agent:'CodeAgent', preview:'扫描完成，发现3处SQL注入风险点...', time:'15分钟前', messages:[
    { role:'user', content:'对我们的Node.js API进行安全扫描', time:'20:15' },
    { role:'agent', content:'🔒 安全扫描已完成，发现以下风险：\n\n🔴 高危(0个)\n🟡 中危(3个)\n🔵 低危(7个)\n\n中危问题：\n1. /api/users/:id - SQL注入风险\n2. /api/search - XSS风险\n3. /api/upload - 文件类型验证不足', time:'20:16' },
  ]},
  { id:'SS003', name:'市场情报收集', agent:'ResearchAgent', preview:'已收集15个竞品数据源，正在整理对比分析...', time:'32分钟前', messages:[
    { role:'user', content:'帮我调研主要竞品的AI功能矩阵', time:'19:58' },
    { role:'agent', content:'正在收集竞品数据...\n\n📊 已分析 8/15 个竞品\n\n初步发现：\n• A产品：强于工作流自动化\n• B产品：NLP能力领先\n• C产品：集成生态最丰富', time:'20:00' },
  ]},
];

export const STATUS_CN = { running:'运行中', pending:'待执行', done:'已完成', failed:'失败', online:'在线', idle:'空闲', offline:'离线' };
export const PRIO_CN = { high:'高', medium:'中', low:'低' };
export const MEM_TYPE_CN = { fact:'事实', conversation:'对话', skill:'技能', context:'上下文' };
