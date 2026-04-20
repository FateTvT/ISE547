import { useEffect, useState } from 'react'
import { Button, Input, Text } from '@chakra-ui/react'
import { useNavigate } from 'react-router-dom'
import { useAiChat, type ChatMessage } from '../hooks/useAiChat'
import { StreamReplyBox } from '../components/chat/StreamReplyBox'
import {
  UserChoiceHistoryPanel,
  type UserChoiceHistoryItem,
} from '../components/chat/UserChoiceHistoryPanel'
import {
  SessionSidebar,
  type ChatSessionItem,
} from '../components/chat/SessionSidebar'
import { clearAccessToken, fetchCurrentUser, type CurrentUser } from '../service/auth.api'
import {
  fetchSessionDetail,
  fetchSessions,
  type PatientSex,
} from '../service/ai_chat.api'
import type { AiChatQuestionCard } from '../schema/ai_chat_stream.schema'

const MIN_ALLOWED_AGE = 18
const MAX_ALLOWED_AGE = 80
const AGE_OPTIONS = Array.from(
  { length: MAX_ALLOWED_AGE - MIN_ALLOWED_AGE + 1 },
  (_, index) => String(MIN_ALLOWED_AGE + index),
)

function createLocalSessionId(): string {
  return `session-${Date.now()}`
}

function isHistoryQuestionCard(value: unknown): value is AiChatQuestionCard {
  if (!value || typeof value !== 'object') {
    return false
  }
  const maybeCard = value as {
    question?: unknown
    question_choices?: unknown
  }
  if (typeof maybeCard.question !== 'string' || !Array.isArray(maybeCard.question_choices)) {
    return false
  }
  return maybeCard.question_choices.every((choice) => {
    if (!choice || typeof choice !== 'object') {
      return false
    }
    const maybeChoice = choice as {
      choice_id?: unknown
      choice?: unknown
      selected?: unknown
    }
    return (
      typeof maybeChoice.choice_id === 'string' &&
      typeof maybeChoice.choice === 'string' &&
      typeof maybeChoice.selected === 'boolean'
    )
  })
}

function parseHistoryQuestionCard(content: string): AiChatQuestionCard | null {
  const raw = content.trim()
  if (!raw) {
    return null
  }

  const tryParse = (value: string): unknown => {
    try {
      return JSON.parse(value)
    } catch {
      return null
    }
  }

  const parsed =
    tryParse(raw) ??
    (raw.startsWith('{') && raw.endsWith('}')
      ? tryParse(raw.replaceAll("'", '"'))
      : null)
  if (!isHistoryQuestionCard(parsed)) {
    return null
  }
  return {
    question: parsed.question,
    question_choices: parsed.question_choices.map((choice) => ({
      choice_id: choice.choice_id,
      choice: choice.choice,
      selected: Boolean(choice.selected),
    })),
  }
}

function isHistoryChoiceEntry(value: unknown): value is UserChoiceHistoryItem {
  if (!value || typeof value !== 'object') {
    return false
  }
  const maybeChoice = value as { choice_id?: unknown; question_card?: unknown }
  if (typeof maybeChoice.choice_id !== 'string') {
    return false
  }
  if (maybeChoice.question_card === undefined || maybeChoice.question_card === null) {
    return true
  }
  return isHistoryQuestionCard(maybeChoice.question_card)
}

export default function HomePage() {
  const navigate = useNavigate()
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null)
  const [authChecking, setAuthChecking] = useState(true)
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [sessionDetailLoading, setSessionDetailLoading] = useState(false)
  const [sessionDetailError, setSessionDetailError] = useState<string | null>(null)
  const [sessionChoiceHistory, setSessionChoiceHistory] = useState<UserChoiceHistoryItem[]>([])
  const [sessions, setSessions] = useState<ChatSessionItem[]>([])
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [prompt, setPrompt] = useState('')
  const [ageInput, setAgeInput] = useState('')
  const [sex, setSex] = useState<PatientSex | ''>('')
  const {
    loading,
    err,
    inputBlocked,
    messages,
    sendMessage,
    submitSelectedQuestionChoice,
    stopStream,
    setSessionId,
    replaceMessages,
    selectQuestionChoice,
  } = useAiChat()

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
    setSessionChoiceHistory([])
    setSessionDetailLoading(true)
    setSelectedSessionId(sessionId)
    const detail = await fetchSessionDetail(sessionId)
    if (!detail) {
      replaceMessages([])
      setSessionChoiceHistory([])
      setSessionDetailError('Failed to load this thread history.')
      setSessionDetailLoading(false)
      return
    }
    setSessionId(sessionId)
    const submittedChoices = (detail.user_choices ?? []).filter(isHistoryChoiceEntry)
    setSessionChoiceHistory(submittedChoices)
    let submittedChoiceCursor = 0
    const mappedHistoryMessages = detail.messages.map<ChatMessage | null>((message, index) => {
        if (message.role === 'user' || message.role === 'assistant') {
          return {
            id: `history-${sessionId}-${index}`,
            role: message.role === 'assistant' ? 'assistant' : 'user',
            content: message.content,
          }
        }
        if (message.role !== 'interrupt') {
          return null
        }
        const submittedChoice = submittedChoices[submittedChoiceCursor] ?? null
        submittedChoiceCursor += 1
        const submittedChoiceId = submittedChoice?.choice_id ?? null
        const questionCard =
          submittedChoice?.question_card ?? parseHistoryQuestionCard(message.content)
        if (!questionCard) {
          return null
        }
        const resolvedCard = submittedChoiceId
          ? {
              ...questionCard,
              question_choices: questionCard.question_choices.map((choice) => ({
                ...choice,
                selected: choice.choice_id === submittedChoiceId,
              })),
            }
          : questionCard
        return {
          id: `history-${sessionId}-${index}`,
          role: 'interrupt',
          content: resolvedCard.question,
          questionCard: resolvedCard,
          questionSubmitted: true,
          questionReadOnly: true,
        }
      })
    const historyMessages = mappedHistoryMessages.filter(
      (message): message is ChatMessage => message !== null,
    )
    replaceMessages(historyMessages)
    setSessionDetailLoading(false)
  }

  const parsedAge = Number(ageInput)
  const hasValidAge =
    ageInput.trim().length > 0 &&
    Number.isFinite(parsedAge) &&
    parsedAge >= MIN_ALLOWED_AGE &&
    parsedAge <= MAX_ALLOWED_AGE
  const demographicsReady = hasValidAge

  const handleSend = async () => {
    if (!demographicsReady) {
      return
    }
    await sendMessage(prompt, parsedAge, (sex || 'undefine') as PatientSex)
  }

  const handleNewDiagnosis = () => {
    stopStream()
    setSelectedSessionId(null)
    setSessionDetailLoading(false)
    setSessionDetailError(null)
    setSessionChoiceHistory([])
    replaceMessages([])
    setPrompt('')
    setSessionId(createLocalSessionId())
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
            <UserChoiceHistoryPanel items={sessionChoiceHistory} />

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
              {!demographicsReady && messages.length === 0 && (
                <div
                  style={{
                    minHeight: '280px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: '12px',
                  }}
                >
                  <div
                    style={{
                      width: 'min(560px, 100%)',
                      borderRadius: '12px',
                      border: '1px solid rgba(255, 255, 255, 0.12)',
                      background: 'rgba(255, 255, 255, 0.03)',
                      padding: '18px',
                    }}
                  >
                    <Text color="gray.100" fontSize="sm" fontWeight="semibold">
                      Please enter your age to get the most accurate diagnosis. Your privacy is our
                      top priority.
                    </Text>
                    <div
                      style={{
                        marginTop: '12px',
                        display: 'flex',
                        gap: '10px',
                        flexWrap: 'wrap',
                        alignItems: 'center',
                      }}
                    >
                      <select
                        value={ageInput}
                        onChange={(event) => setAgeInput(event.target.value)}
                        style={{
                          height: '40px',
                          minWidth: '190px',
                          borderRadius: '6px',
                          border: '1px solid rgba(255, 255, 255, 0.24)',
                          background: 'rgba(255, 255, 255, 0.04)',
                          color: 'white',
                          padding: '0 10px',
                        }}
                      >
                        <option value="" style={{ color: 'black' }}>
                          Select age ({MIN_ALLOWED_AGE}-{MAX_ALLOWED_AGE})
                        </option>
                        {AGE_OPTIONS.map((age) => (
                          <option key={age} value={age} style={{ color: 'black' }}>
                            {age}
                          </option>
                        ))}
                      </select>
                      <select
                        value={sex}
                        onChange={(event) => setSex(event.target.value as PatientSex | '')}
                        style={{
                          height: '40px',
                          minWidth: '190px',
                          borderRadius: '6px',
                          border: '1px solid rgba(255, 255, 255, 0.24)',
                          background: 'rgba(255, 255, 255, 0.04)',
                          color: 'white',
                          padding: '0 10px',
                        }}
                      >
                        <option value="" style={{ color: 'black' }}>
                          Sex (optional)
                        </option>
                        <option value="male" style={{ color: 'black' }}>
                          Male
                        </option>
                        <option value="female" style={{ color: 'black' }}>
                          Female
                        </option>
                        <option value="undefine" style={{ color: 'black' }}>
                          Prefer not to say
                        </option>
                      </select>
                    </div>
                    {!demographicsReady && (
                      <Text color="orange.200" fontSize="xs" mt={2}>
                        Please select your age before typing.
                      </Text>
                    )}
                  </div>
                </div>
              )}
              <StreamReplyBox
                messages={messages}
                loading={loading}
                onSelectQuestionChoice={selectQuestionChoice}
                onSubmitQuestionChoice={submitSelectedQuestionChoice}
              />
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
                disabled={loading || inputBlocked || !demographicsReady}
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
                disabled={inputBlocked || !demographicsReady || !prompt.trim()}
              >
                Send
              </Button>
              <Button
                variant="outline"
                color="white"
                borderColor="rgba(255, 255, 255, 0.32)"
                onClick={handleNewDiagnosis}
                bg="rgba(255, 255, 255, 0.10)"
                _hover={{ bg: 'rgba(255, 255, 255, 0.16)' }}
              >
                New Diagnosis
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
