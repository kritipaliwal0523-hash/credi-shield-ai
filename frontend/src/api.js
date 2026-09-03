import axios from 'axios'

export const API_BASE = 'http://localhost:8000'

export function handleAuthError(err) {
  if (err.response?.status === 401) {
    localStorage.removeItem('access_token')
    window.location.href = '/'
    return true
  }
  return false
}

export const api = axios.create({
  baseURL: API_BASE,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
