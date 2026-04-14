import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Provider } from '@/components/ui/provider'
import './index.css'
import App from './App.tsx'
import { client } from './client/client.gen'
import { createConfig } from './client/client'
import { getAccessToken } from './service/auth.api'

// 配置客户端基础URL
client.setConfig(createConfig({
  baseUrl: import.meta.env.VITE_API_URL,
  auth: () => getAccessToken(),
}))


createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Provider>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </Provider>
  </StrictMode>,
)
