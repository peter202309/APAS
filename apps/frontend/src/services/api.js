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
    }
};
