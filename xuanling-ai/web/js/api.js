/**
 * 玄灵AI API 客户端
 */

const API_BASE = (typeof window !== 'undefined' ? (window.location.origin + '/api') : 'http://localhost:8000/api');

class APIClient {
    async request(endpoint, options = {}) {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });
        if (!response.ok) {
            throw new Error(`API Error: ${response.status}`);
        }
        return response.json();
    }

    // 对话
    async chat(message, projectId = null) {
        return this.request('/chat', {
            method: 'POST',
            body: JSON.stringify({ message, project_id: projectId })
        });
    }

    // 项目
    async getProjects() {
        return this.request('/projects');
    }

    async createProject(data) {
        return this.request('/projects', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    // 记忆
    async getMemory(projectId = null) {
        const url = projectId ? `/memory?project_id=${projectId}` : '/memory';
        return this.request(url);
    }

    async createMemory(data) {
        return this.request('/memory', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    // 任务
    async getTasks() {
        return this.request('/tasks');
    }

    // 代理
    async getAgents() {
        return this.request('/agents');
    }

    // Skills
    async getSkills() {
        return this.request('/skills');
    }

    // 监控
    async getMonitor() {
        return this.request('/monitor');
    }
}

export const api = new APIClient();
export default api;
