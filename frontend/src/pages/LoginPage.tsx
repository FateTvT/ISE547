import { useEffect, useState } from 'react'
import { Button, Input, Text } from '@chakra-ui/react'
import { useNavigate } from 'react-router-dom'
import {
  clearAccessToken,
  fetchCurrentUser,
  login,
  type CurrentUser,
} from '../service/auth.api'

export default function LoginPage() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [authLoading, setAuthLoading] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null)

  useEffect(() => {
    const loadCurrentUser = async () => {
      const user = await fetchCurrentUser()
      if (user) {
        setCurrentUser(user)
        navigate('/home', { replace: true })
      }
    }
    void loadCurrentUser()
  }, [navigate])

  const handleLogin = async () => {
    if (authLoading) {
      return
    }
    setAuthError(null)
    setAuthLoading(true)
    try {
      await login({
        username: username.trim(),
        password,
      })
      const user = await fetchCurrentUser()
      if (!user) {
        throw new Error('Login succeeded, but failed to load current user.')
      }
      setCurrentUser(user)
      navigate('/home', { replace: true })
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : 'Login failed')
      clearAccessToken()
      setCurrentUser(null)
    } finally {
      setAuthLoading(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        padding: '32px 16px',
        background: '#171923',
      }}
    >
      <div
        style={{
          maxWidth: '560px',
          margin: '0 auto',
          background: '#1f2937',
          borderRadius: '16px',
          padding: '24px',
          boxShadow: '0 10px 30px rgba(0, 0, 0, 0.25)',
        }}
      >
        <Text fontSize="3xl" fontWeight="bold" color="white">
          Login
        </Text>
        <Text color="gray.300" mt={2}>
          Sign in to access AI chat.
        </Text>

        <div
          style={{
            display: 'flex',
            gap: '12px',
            marginTop: '16px',
          }}
        >
          <Input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="Username"
            color="white"
            bg="rgba(255, 255, 255, 0.04)"
            borderColor="rgba(255, 255, 255, 0.24)"
            _placeholder={{ color: 'gray.400' }}
            disabled={authLoading || Boolean(currentUser)}
          />
          <Input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Password"
            color="white"
            bg="rgba(255, 255, 255, 0.04)"
            borderColor="rgba(255, 255, 255, 0.24)"
            _placeholder={{ color: 'gray.400' }}
            disabled={authLoading || Boolean(currentUser)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                void handleLogin()
              }
            }}
          />
          <Button
            bg="#14b8a6"
            color="white"
            _hover={{ bg: '#0f9f90' }}
            onClick={() => void handleLogin()}
            loading={authLoading}
            disabled={Boolean(currentUser)}
          >
            Login
          </Button>
        </div>

        {authError && (
          <Text color="red.300" mt={3}>
            Auth error: {authError}
          </Text>
        )}
      </div>
    </div>
  )
}
