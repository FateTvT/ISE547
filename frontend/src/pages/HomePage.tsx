import { useEffect, useState } from 'react'
import { Button, Input, Text } from '@chakra-ui/react'
import { useNavigate } from 'react-router-dom'
import { useAiChat } from '../hooks/useAiChat'
import { StreamReplyBox } from '../components/chat/StreamReplyBox'
import { clearAccessToken, fetchCurrentUser, type CurrentUser } from '../service/auth.api'

export default function HomePage() {
  const navigate = useNavigate()
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null)
  const [authChecking, setAuthChecking] = useState(true)
  const [prompt, setPrompt] = useState('')
  const { loading, err, messages, sendMessage, stopStream } = useAiChat()

  useEffect(() => {
    const loadCurrentUser = async () => {
      const user = await fetchCurrentUser()
      if (!user) {
        clearAccessToken()
        navigate('/login', { replace: true })
        return
      }
      setCurrentUser(user)
      setAuthChecking(false)
    }
    void loadCurrentUser()
  }, [navigate])

  const handleLogout = () => {
    clearAccessToken()
    navigate('/login', { replace: true })
  }

  const handleSend = async () => {
    await sendMessage(prompt)
  }

  if (authChecking) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#171923',
        }}
      >
        <Text color="gray.300">Checking your session...</Text>
      </div>
    )
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
          maxWidth: '960px',
          margin: '0 auto',
          background: '#1f2937',
          borderRadius: '16px',
          padding: '24px',
          boxShadow: '0 10px 30px rgba(0, 0, 0, 0.25)',
        }}
      >
        <Text fontSize="3xl" fontWeight="bold" color="white">
          AI Chat
        </Text>
        <Text color="gray.300" mt={2}>
          Send a message and get real-time SSE responses.
        </Text>
        <Text color="gray.300" mt={2}>
          Signed in as {currentUser?.username} ({currentUser?.email})
        </Text>

        <div
          style={{
            display: 'flex',
            justifyContent: 'flex-end',
            marginTop: '16px',
          }}
        >
          <Button
            variant="outline"
            color="white"
            borderColor="rgba(255, 255, 255, 0.32)"
            onClick={handleLogout}
          >
            Logout
          </Button>
        </div>

        <div
          style={{
            display: 'flex',
            gap: '12px',
            marginTop: '20px',
          }}
        >
          <Input
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="Ask something..."
            color="white"
            bg="rgba(255, 255, 255, 0.04)"
            borderColor="rgba(255, 255, 255, 0.24)"
            _placeholder={{ color: 'gray.400' }}
            disabled={loading}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                void handleSend()
              }
            }}
          />
          <Button
            bg="#3182ce"
            color="white"
            _hover={{ bg: '#2b6cb0' }}
            onClick={() => void handleSend()}
            loading={loading}
          >
            Send
          </Button>
          <Button
            variant="outline"
            color="white"
            borderColor="rgba(255, 255, 255, 0.32)"
            onClick={stopStream}
            disabled={!loading}
          >
            Stop
          </Button>
        </div>

        {err && (
          <Text color="red.300" mt={4}>
            Error: {err}
          </Text>
        )}

        <div
          style={{
            marginTop: '24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
            minHeight: '420px',
          }}
        >
          <StreamReplyBox messages={messages} loading={loading} />
        </div>
      </div>
    </div>
  )
}
