import axios from 'axios';

// Use /api path - proxied by Vite in dev, nginx in production
const baseURL = '/api';

export const api = axios.create({
  baseURL,
  timeout: 30000,
});

// Add response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);
