import { Button, Text } from '@chakra-ui/react'
import type { CurrentUser } from '../../service/auth.api'
import { SidebarUserCard } from './SidebarUserCard'

export type ChatSessionItem = {
  id: string
  name: string
}

type SessionSidebarProps = {
  currentUser: CurrentUser | null
  sessions: ChatSessionItem[]
  selectedSessionId: string | null
  loading: boolean
  onSelect: (sessionId: string) => void
  onRefresh: () => void
  onLogout: () => void
}

export function SessionSidebar({
  currentUser,
  sessions,
  selectedSessionId,
  loading,
  onSelect,
  onRefresh,
  onLogout,
}: SessionSidebarProps) {
  return (
    <div
      style={{
        width: '280px',
        minHeight: '680px',
        borderRight: '1px solid rgba(255, 255, 255, 0.12)',
        paddingRight: '16px',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div style={{ flex: 1, minHeight: 0 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '12px',
          }}
        >
          <Text color="white" fontWeight="bold">
            Threads
          </Text>
          <Button
            size="xs"
            onClick={onRefresh}
            loading={loading}
            bg="rgba(255, 255, 255, 0.10)"
            color="white"
            border="1px solid rgba(255, 255, 255, 0.25)"
            _hover={{ bg: 'rgba(255, 255, 255, 0.16)' }}
          >
            Refresh
          </Button>
        </div>
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            maxHeight: '540px',
            overflowY: 'auto',
          }}
        >
          {sessions.length === 0 ? (
            <Text color="gray.400" fontSize="sm">
              No threads yet.
            </Text>
          ) : (
            sessions.map((session) => (
              <button
                type="button"
                key={session.id}
                onClick={() => onSelect(session.id)}
                style={{
                  textAlign: 'left',
                  background:
                    selectedSessionId === session.id
                      ? 'rgba(49, 130, 206, 0.28)'
                      : 'rgba(255, 255, 255, 0.04)',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  borderRadius: '10px',
                  padding: '10px',
                  cursor: 'pointer',
                }}
              >
                <Text
                  color="white"
                  fontSize="sm"
                  style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
                >
                  {session.name || 'Untitled thread'}
                </Text>
              </button>
            ))
          )}
        </div>
      </div>
      <SidebarUserCard user={currentUser} onLogout={onLogout} />
    </div>
  )
}
