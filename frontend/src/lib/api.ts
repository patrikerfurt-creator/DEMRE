import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor: add auth token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const authStr = localStorage.getItem('demre-auth')
    if (authStr) {
      try {
        const auth = JSON.parse(authStr)
        const token = auth?.state?.token
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
      } catch {}
    }
    return config
  },
  (error) => Promise.reject(error)
)

let isRefreshing = false
let failedQueue: Array<{
  resolve: (value: unknown) => void
  reject: (reason?: unknown) => void
}> = []

function processQueue(error: AxiosError | null, token: string | null = null) {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token)
    }
  })
  failedQueue = []
}

// Response interceptor: handle 401 with token refresh
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`
          return api(originalRequest)
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      const authStr = localStorage.getItem('demre-auth')
      let refreshToken: string | null = null
      if (authStr) {
        try {
          refreshToken = JSON.parse(authStr)?.state?.refreshToken
        } catch {}
      }

      if (!refreshToken) {
        processQueue(error, null)
        isRefreshing = false
        window.location.href = '/login'
        return Promise.reject(error)
      }

      try {
        const response = await axios.post('/api/v1/auth/refresh', {
          refresh_token: refreshToken,
        })
        const { access_token, refresh_token: newRefreshToken, user } = response.data

        // Update store
        const { useAuthStore } = await import('@/store/authStore')
        useAuthStore.getState().setAuth(access_token, newRefreshToken, user)

        processQueue(null, access_token)
        originalRequest.headers.Authorization = `Bearer ${access_token}`
        return api(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError as AxiosError, null)
        const { useAuthStore } = await import('@/store/authStore')
        useAuthStore.getState().clearAuth()
        window.location.href = '/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

/** Dokument mit Auth-Header laden und in neuem Tab öffnen */
export async function openDocument(url: string): Promise<void> {
  const response = await api.get(url, { responseType: 'blob' })
  const contentType = response.headers['content-type'] || 'application/octet-stream'
  const blob = new Blob([response.data], { type: contentType })
  const objectUrl = URL.createObjectURL(blob)
  window.open(objectUrl, '_blank')
  setTimeout(() => URL.revokeObjectURL(objectUrl), 15000)
}

export default api
