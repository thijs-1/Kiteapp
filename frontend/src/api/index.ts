import axios from 'axios';

// Use Vite proxy in development, direct URL in production
const baseURL = import.meta.env.PROD
  ? import.meta.env.VITE_API_URL || 'http://localhost:8000'
  : '/api';

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
