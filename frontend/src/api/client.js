import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const client = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

// Request interceptor
client.interceptors.request.use((config) => {
  if (!(config.data instanceof FormData)) {
    config.headers['Content-Type'] = 'application/json';
  }
  return config;
});

// Response interceptor
client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail || error.message;

    if (status === 422) {
      console.error('Validation error:', detail);
      return Promise.reject(new Error(`Validation error: ${JSON.stringify(detail)}`));
    }
    if (status === 503) {
      return Promise.reject(new Error('Model not loaded. Please train the model first.'));
    }
    console.error(`API error (${status}):`, detail);
    return Promise.reject(new Error(detail || 'An unexpected error occurred'));
  }
);

// ── Prediction ──
export const predictSalary = (payload) =>
  client.post('/api/v1/predict', payload);

export const predictFromResume = (file) => {
  const formData = new FormData();
  formData.append('file', file);
  // Do not set Content-Type manually, let Axios set it with the boundary automatically
  return client.post('/api/v1/predict/resume', formData);
};

// ── Jobs ──
export const searchJobs = (params) =>
  client.get('/api/v1/jobs', { params });

export const getJob = (id) =>
  client.get(`/api/v1/jobs/${id}`);

// ── Insights ──
export const getSalaryByCity = (keyword) =>
  client.get('/api/v1/insights/salary-by-city', { params: keyword ? { keyword } : {} });

export const getTopSkills = (city, seniority) =>
  client.get('/api/v1/insights/top-skills', {
    params: { ...(city && { city }), ...(seniority && { seniority }) },
  });

export const getSalaryBySeniority = () =>
  client.get('/api/v1/insights/salary-by-seniority');

export const getRemoteVsOnsite = () =>
  client.get('/api/v1/insights/remote-vs-onsite');

export const getMarketSummary = () =>
  client.get('/api/v1/insights/market-summary');

export default client;
