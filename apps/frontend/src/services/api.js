import axios from 'axios';

const API_BASE = 'http://localhost:8080';

export const scraperService = {
    async launchTask(taskData) {
        const response = await axios.post(`${API_BASE}/tasks/scrape`, taskData);
        return response.data;
    },

    async getResults() {
        const response = await axios.get(`${API_BASE}/results`);
        return response.data;
    },

    async getLogs() {
        const response = await axios.get(`${API_BASE}/logs`);
        return response.data;
    },

    async getBatches() {
        const response = await axios.get(`${API_BASE}/batches`);
        return response.data;
    },

    async getBatchDetails(batchId) {
        const response = await axios.get(`${API_BASE}/batches/${batchId}`);
        return response.data;
    },

    async uploadBatch(file) {
        const formData = new FormData();
        formData.append('file', file);
        const response = await axios.post(`${API_BASE}/tasks/batch-upload`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
        return response.data;
    },

    async generateAIReport(params) {
        // params: { batch_id: "...", origin: "SHA", destination: "YVR" }
        const response = await axios.post(`${API_BASE}/ai/analyze`, params);
        return response.data;
    },

    async uploadComparisonFiles(files, userPrompt = null) {
        const formData = new FormData();
        Array.from(files).forEach(file => {
            formData.append("files", file);
        });
        if (userPrompt) {
            formData.append("user_prompt", userPrompt);
        }
        const response = await axios.post(`${API_BASE}/ai/compare_files`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
        return response.data;
    },

    async compareBatches(batchIds, userPrompt = null) {
        const response = await axios.post(`${API_BASE}/ai/compare_batches`, {
            batch_ids: batchIds,
            user_prompt: userPrompt
        });
        return response.data;
    },

    getBatchExportUrl(batchId) {
        return `${API_BASE}/export/csv/${batchId}`;
    },

    async deleteBatch(batchId) {
        const response = await axios.delete(`${API_BASE}/batches/${batchId}`);
        return response.data;
    }
};
