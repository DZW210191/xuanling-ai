# 玄灵AI 修复方案（可直接开工）

## 目标
先把核心链路修成“能稳定用”，再清理兼容壳和重复逻辑。

## 修复顺序
1. 统一前后端接口
2. 补齐项目 CRUD
3. 补齐记忆 CRUD
4. 补齐子代理 CRUD/详情/任务/记忆
5. 统一设置保存逻辑
6. 清理前端对不存在接口的调用
7. 统一返回字段与错误处理
8. 末尾再做接口清理和重构

---

## 1) 统一前后端接口

### 问题
前端正在调用：
- `/projects/json`
- `/memory/json`
- `/agents/{id}`
- `/agents/{id}/memory`
- `/agents/{id}/tasks`

后端当前没有这些路由，或仅有静态空壳。

### 方案
两种做法二选一：
- **推荐**：改前端，全部对齐后端已有标准路由
- **临时兼容**：后端补兼容路由，先让功能跑起来

### 我建议
先做兼容，降低改动风险；同时把前端逐步切到标准路由。

---

## 2) 后端必须补齐的代码点（main.py）

### 2.1 项目 CRUD
#### 要新增/修正的路由
- `GET /projects` -> 返回项目列表
- `POST /projects` -> 创建项目
- `PUT /projects/{project_id}` -> 更新项目
- `DELETE /projects/{project_id}` -> 删除项目

#### 现状问题
- 当前 `POST/PUT/DELETE /projects` 是空返回，不会真正落库。
- 前端项目详情保存、删除虽然会打接口，但后端没做实事。

#### 修改建议
把现有 `create_project / update_project / delete_project` 这三个函数挂上路由，并让它们真正操作 `_data["projects"]`。

#### 代码修改点
在 `main.py` 中找到：
- `def get_projects_list()`
- `def create_project(project: Project)`
- `def update_project(project_id: int, project: Project)`
- `def delete_project(project_id: int)`

然后：
- 给 `get_projects_list` 加上 `@app.get("/projects")`
- 给 `create_project` 加上 `@app.post("/projects")`
- 给 `update_project` 加上 `@app.put("/projects/{project_id}")`
- 给 `delete_project` 加上 `@app.delete("/projects/{project_id}")`

同时让这些函数返回统一 JSON 结构。

---

### 2.2 记忆 CRUD
#### 要新增/修正的路由
- `GET /memory`
- `POST /memory`
- `DELETE /memory/{memory_id}`

#### 现状问题
- 前端新增记忆打的是 `/memory/json`，后端不存在。
- 后端已有 `/api/memory`，但前端没用。

#### 修改建议
- 先在后端补一条兼容路由：`POST /memory/json`
- 再把前端改成统一走 `POST /memory`

#### 代码修改点
在 `main.py` 里：
- 让 `create_memory_compat` 真正调用 `save_memory()`
- 增加 `POST /memory/json` 兼容接口（短期过渡）
- `DELETE /memory/{memory_id}` 继续保留，但要确保前端调用一致

---

### 2.3 子代理模块
#### 要新增/修正的路由
- `GET /agents`
- `POST /agents`
- `PUT /agents/{agent_id}`
- `DELETE /agents/{agent_id}`
- `GET /agents/{agent_id}/memory`
- `POST /agents/{agent_id}/memory`
- `GET /agents/{agent_id}/tasks`

#### 现状问题
- 前端有完整 UI，后端只有静态 `GET /agents`。
- 其他接口全缺。

#### 修改建议
如果短期不打算做真正的 agent 引擎，就先做**数据层假实现**：
- 先用 JSON 文件保存 agents
- memory 和 tasks 也先保存到内存/JSON
- 保证 UI 所有按钮都不报错

#### 代码修改点
在 `main.py`：
- 新增 `AGENTS_FILE` 或在 `_data` 中增加 `agents / agent_memories / agent_tasks`
- 实现 CRUD
- 返回字段统一用前端正在读的：
  - `id`
  - `name`
  - `description`
  - `status`
  - `tasks_count`
  - `success_rate`

---

### 2.4 设置保存
#### 现状问题
- 前端主要调用 `/config`
- 后端真正保存设置的是 `/api/settings`
- `POST /config` 目前是空壳

#### 修改建议
二选一：
- **推荐**：前端改成调用 `/api/settings`
- **兼容方案**：`/config` 直接转发到 `/api/settings`

#### 代码修改点
在 `main.py`：
- 让 `POST /config` 解析请求体并写入 `app_settings`
- `GET /config` 返回和前端一致的字段
- 保证 `/models`、`/config`、`/api/settings` 三者字段一致

---

### 2.5 项目文件管理
#### 现状问题
- 前端能看文件、保存文件
- 后端接口返回空内容，等于没做

#### 修改建议
短期先别做完整文件系统，先让它“别骗人”：
- `GET /project-manager/projects/{project_name}/files/{file_path}` 返回明确错误或真实内容
- `PUT ...` 至少要写入本地项目目录
- `DELETE ...` 不建议先开放，除非能真的删除

#### 代码修改点
先判断项目目录是否存在，再读取/写入真实文件；如果没有真实项目目录，就直接返回 `404`，别伪装成功。

---

## 3) 前端必须改的点（server/static/index.html）

### 3.1 项目新增
#### 现状
`confirmAddProject()` 调用：
- `POST /projects/json`

#### 修复
改为：
- `POST /projects`

#### 代码点
搜索：
- `fetch(API_BASE + '/projects/json'`

替换成：
- `fetch(API_BASE + '/projects'`

---

### 3.2 记忆新增/编辑
#### 现状
- 新增：`POST /memory/json`
- 编辑：先删再走 `/memory/json`

#### 修复
改为：
- 新增直接 `POST /memory`
- 编辑时先 `DELETE /memory/{id}`，再 `POST /memory`

#### 代码点
搜索：
- `fetch(API_BASE + '/memory/json'`

替换成：
- `fetch(API_BASE + '/memory'`

同时把 `tags` 从字符串改成数组：
- `tags: tags ? tags.split(',').map(t => t.trim()).filter(Boolean) : []`

---

### 3.3 子代理保存/删除
#### 现状
前端调用了后端没有的接口。

#### 修复
确保这些接口存在：
- `POST /agents`
- `PUT /agents/{id}`
- `DELETE /agents/{id}`
- `GET/POST /agents/{id}/memory`
- `GET /agents/{id}/tasks`

如果后端暂时不做真实逻辑，至少返回正确结构，让页面不报错。

---

### 3.4 设置页
#### 现状
前端同时维护了本地 localStorage + `/config`。

#### 修复建议
- 保留 localStorage 作为缓存
- 真正生效以 `/api/settings` 或统一后的 `/config` 为准
- `loadSettings()` 和 `saveSettings()` 的字段名统一用 `apiUrl / apiKey / model`

---

## 4) 字段统一

### 后端返回建议
项目：
```json
{
  "id": 1,
  "name": "xxx",
  "description": "xxx",
  "icon": "📁",
  "status": "开发中",
  "progress": 0,
  "tasks": 0,
  "memory": 0
}
```

记忆：
```json
{
  "id": 1,
  "title": "xxx",
  "content": "xxx",
  "tags": ["a", "b"],
  "project_id": null,
  "importance": 1
}
```

子代理：
```json
{
  "id": 1,
  "name": "xxx",
  "description": "xxx",
  "status": "running",
  "tasks_count": 12,
  "success_rate": 0.92
}
```

---

## 5) 我建议的最小可交付改动集
如果你想先让它“立刻可用”，先做这 5 个：

1. `POST /projects` 真正创建项目
2. `POST /memory` 真正创建记忆
3. 前端把 `/projects/json` 改成 `/projects`
4. 前端把 `/memory/json` 改成 `/memory`
5. 后端补齐 `POST/PUT/DELETE /agents` 和子接口的占位实现

做到这一步，UI 就不会一堆按钮点了没反应。

---

## 6) 验证清单
改完后逐项检查：
- 首页能打开
- `/api/chat` 能返回
- 项目能新增、编辑、删除
- 记忆能新增、编辑、删除
- 子代理面板打开不报错
- 设置页保存后刷新还在
- `/health`、`/config`、`/models` 返回字段一致

---

## 7) 你现在最该先改的文件
- `xuanling-ai/server/main.py`
- `xuanling-ai/server/static/index.html`
- `xuanling-ai/web/js/api.js`

如果你要，我下一条可以直接给你出：
- **“main.py 逐段修改补丁清单”**
- 或者 **“前端 index.html 需要替换的具体行/函数”**