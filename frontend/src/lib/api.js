import axios from "axios";

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({
    baseURL: API,
    withCredentials: true,
});

export async function authSession(sessionId) {
    const { data } = await api.post("/auth/session", { session_id: sessionId });
    return data;
}

export async function authMe() {
    const { data } = await api.get("/auth/me");
    return data;
}

export async function authLogout() {
    const { data } = await api.post("/auth/logout");
    return data;
}

export const Jobs = {
    list: () => api.get("/jobs").then((r) => r.data),
    get: (id) => api.get(`/jobs/${id}`).then((r) => r.data),
    scrape: (limit = 6) => api.post("/jobs/scrape", { limit }).then((r) => r.data),
    del: (id) => api.delete(`/jobs/${id}`).then((r) => r.data),
    setStatus: (id, status) => api.post(`/jobs/${id}/status`, { status }).then((r) => r.data),
    prospects: (id) => api.get(`/jobs/${id}/prospects`).then((r) => r.data),
    campaigns: (id) => api.get(`/jobs/${id}/campaigns`).then((r) => r.data),
    findProspects: (id, count = 3) =>
        api.post(`/jobs/${id}/prospects/find`, { count }).then((r) => r.data),
    coverLetter: (id, body = {}) =>
        api.post(`/jobs/${id}/cover-letter`, body).then((r) => r.data),
};

export const Prospects = {
    list: () => api.get("/prospects").then((r) => r.data),
};

export const Campaigns = {
    list: () => api.get("/campaigns").then((r) => r.data),
    generate: (payload) => api.post("/campaigns/generate", payload).then((r) => r.data),
    send: (id) => api.post("/campaigns/send", { campaign_id: id }).then((r) => r.data),
    followup: (id) => api.post(`/campaigns/${id}/followup`).then((r) => r.data),
};

export const Skills = {
    list: () => api.get("/skills").then((r) => r.data),
    aggregate: () => api.post("/skills/aggregate").then((r) => r.data),
};

export const Resumes = {
    list: () => api.get("/resumes").then((r) => r.data),
    create: (body) => api.post("/resumes", body).then((r) => r.data),
    del: (id) => api.delete(`/resumes/${id}`).then((r) => r.data),
    setDefault: (id) => api.post(`/resumes/${id}/default`).then((r) => r.data),
};

export const Scheduler = {
    status: () => api.get("/scheduler/status").then((r) => r.data),
    run: () => api.post("/scheduler/run").then((r) => r.data),
};

export const Dashboard = {
    summary: () => api.get("/dashboard/summary").then((r) => r.data),
};
