import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Provider } from '@/components/ui/provider'
import './index.css'
import App from './App.tsx'
import { client } from './client/client.gen'
import { createConfig } from './client/client'

// 配置客户端基础URL
client.setConfig(createConfig({
  baseUrl: import.meta.env.VITE_API_URL
}))


createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Provider>
      <App />
    </Provider>
  </StrictMode>,
)
