import { useEffect, useState } from 'react'
import { Button, Input, Text } from '@chakra-ui/react'
import { useNavigate } from 'react-router-dom'
import { useAiChat, type ChatMessage } from '../hooks/useAiChat'
import { StreamReplyBox } from '../components/chat/StreamReplyBox'
import {
  SessionSidebar,
  type ChatSessionItem,
} from '../components/chat/SessionSidebar'
import { clearAccessToken, fetchCurrentUser, type CurrentUser } from '../service/auth.api'
import { fetchSessionDetail, fetchSessions } from '../service/ai_chat.api'

export default function HomePage() {
  const navigate = useNavigate()
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null)
  const [authChecking, setAuthChecking] = useState(true)
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [sessionDetailLoading, setSessionDetailLoading] = useState(false)
  const [sessionDetailError, setSessionDetailError] = useState<string | null>(null)
  const [sessions, setSessions] = useState<ChatSessionItem[]>([])
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [prompt, setPrompt] = useState('')
  const { loading, err, messages, sendMessage, stopStream, setSessionId, replaceMessages } =
    useAiChat()

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

  const loadSessions = async () => {
    setSessionsLoading(true)
    const allSessions = await fetchSessions()
    setSessions(allSessions)
    setSessionsLoading(false)
  }

  useEffect(() => {
    if (!currentUser) {
      return
    }
    void loadSessions()
  }, [currentUser])

  const handleSelectSession = async (sessionId: string) => {
    if (selectedSessionId === sessionId) {
      return
    }
    stopStream()
    setSessionDetailError(null)
    setSessionDetailLoading(true)
    setSelectedSessionId(sessionId)
    const detail = await fetchSessionDetail(sessionId)
    if (!detail) {
      replaceMessages([])
      setSessionDetailError('Failed to load this thread history.')
      setSessionDetailLoading(false)
      return
    }
    setSessionId(sessionId)
    const historyMessages: ChatMessage[] = detail.messages
      .filter((message) => message.role === 'user' || message.role === 'assistant')
      .map((message, index) => ({
        id: `history-${sessionId}-${index}`,
        role: message.role === 'assistant' ? 'assistant' : 'user',
        content: message.content,
      }))
    replaceMessages(historyMessages)
    setSessionDetailLoading(false)
  }

  const handleSend = async () => {
    await sendMessage(prompt)
  }

  if (authChecking) {
    return (
      <div
        style={{
          height: '100dvh',
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
        height: '100dvh',
        padding: '32px 16px',
        background: '#171923',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          maxWidth: '1120px',
          margin: '0 auto',
          background: '#1f2937',
          borderRadius: '16px',
          padding: '24px',
          boxShadow: '0 10px 30px rgba(0, 0, 0, 0.25)',
          height: 'calc(100dvh - 64px)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            display: 'flex',
            gap: '20px',
            height: '100%',
            minHeight: 0,
          }}
        >
          <SessionSidebar
            currentUser={currentUser}
            sessions={sessions}
            selectedSessionId={selectedSessionId}
            loading={sessionsLoading}
            onSelect={(sessionId) => void handleSelectSession(sessionId)}
            onRefresh={() => void loadSessions()}
            onLogout={handleLogout}
          />
          <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
            <Text fontSize="3xl" fontWeight="bold" color="white">
              ISE 547 Project
            </Text>
            <Text color="gray.500" mt={1} fontSize="xs">
              Select a session on the left to load its history.
            </Text>

            {err && (
              <Text color="red.300" mt={4}>
                Error: {err}
              </Text>
            )}
            {sessionDetailError && (
              <Text color="red.300" mt={2}>
                {sessionDetailError}
              </Text>
            )}
            {sessionDetailLoading && (
              <Text color="gray.300" mt={2}>
                Loading thread history...
              </Text>
            )}

            <div
              className="custom-scrollbar"
              style={{
                marginTop: '24px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                flex: 1,
                minHeight: 0,
                overflowY: 'auto',
                paddingRight: '6px',
              }}
            >
              <StreamReplyBox messages={messages} loading={loading} />
            </div>

            <div
              style={{
                display: 'flex',
                gap: '12px',
                marginTop: '12px',
                paddingTop: '12px',
                borderTop: '1px solid rgba(255, 255, 255, 0.1)',
                flexShrink: 0,
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
                bg="rgba(255, 255, 255, 0.10)"
                _hover={{ bg: 'rgba(255, 255, 255, 0.16)' }}
              >
                Stop
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
