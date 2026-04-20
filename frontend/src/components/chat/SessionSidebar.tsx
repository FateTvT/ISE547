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
  deletingSessionId?: string | null
  onSelect: (sessionId: string) => void
  onDelete: (sessionId: string) => void
  onRefresh: () => void
  onLogout: () => void
}

export function SessionSidebar({
  currentUser,
  sessions,
  selectedSessionId,
  loading,
  deletingSessionId = null,
  onSelect,
  onDelete,
  onRefresh,
  onLogout,
}: SessionSidebarProps) {
  const primaryColor = '#122E8A'
  const secondaryColor = '#5A6FB2'
  const textPrimary = '#1E2A4A'
  const textMuted = '#5B678A'
  const borderColor = '#C9D3EA'

  return (
    <div
      style={{
        width: '280px',
        height: '100%',
        minHeight: 0,
        borderRight: `1px solid ${borderColor}`,
        paddingRight: '16px',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '12px',
          }}
        >
          <Text color={primaryColor} fontWeight="bold">
            History
          </Text>
          <Button
            size="xs"
            onClick={onRefresh}
            loading={loading}
            bg="#E8EDFB"
            color={secondaryColor}
            border={`1px solid ${secondaryColor}`}
            _hover={{ bg: '#DCE4F9' }}
          >
            Refresh
          </Button>
        </div>
        <div
          className="custom-scrollbar"
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            paddingRight: '4px',
          }}
        >
          {sessions.length === 0 ? (
            <Text color={textMuted} fontSize="sm">
              No threads yet.
            </Text>
          ) : (
            sessions.map((session) => (
              <div
                key={session.id}
                style={{
                  background:
                    selectedSessionId === session.id
                      ? 'rgba(18, 46, 138, 0.16)'
                      : '#F8FAFF',
                  border: `1px solid ${borderColor}`,
                  borderRadius: '10px',
                  position: 'relative',
                  transition: 'background 0.15s ease',
                }}
                onMouseEnter={(event) => {
                  const deleteButton = event.currentTarget.querySelector(
                    '[data-session-delete-button]',
                  ) as HTMLButtonElement | null
                  if (deleteButton) {
                    deleteButton.style.opacity = '1'
                    deleteButton.style.pointerEvents = 'auto'
                  }
                }}
                onMouseLeave={(event) => {
                  const deleteButton = event.currentTarget.querySelector(
                    '[data-session-delete-button]',
                  ) as HTMLButtonElement | null
                  if (deleteButton) {
                    deleteButton.style.opacity = '0'
                    deleteButton.style.pointerEvents = 'none'
                  }
                }}
              >
                <button
                  type="button"
                  onClick={() => onSelect(session.id)}
                  style={{
                    textAlign: 'left',
                    padding: '10px 42px 10px 10px',
                    cursor: 'pointer',
                    width: '100%',
                    background: 'transparent',
                    border: 'none',
                    borderRadius: '10px',
                  }}
                >
                  <Text
                    color={textPrimary}
                    fontSize="sm"
                    style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
                  >
                    {session.name || 'Untitled thread'}
                  </Text>
                </button>
                <button
                  type="button"
                  data-session-delete-button
                  aria-label={`Delete ${session.name || 'thread'}`}
                  disabled={loading || deletingSessionId === session.id}
                  onClick={(event) => {
                    event.stopPropagation()
                    onDelete(session.id)
                  }}
                  style={{
                    position: 'absolute',
                    right: '8px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    border: 'none',
                    background: 'transparent',
                    color: '#f87171',
                    fontSize: '16px',
                    lineHeight: 1,
                    cursor: loading || deletingSessionId === session.id ? 'not-allowed' : 'pointer',
                    opacity: deletingSessionId === session.id ? 1 : 0,
                    pointerEvents: deletingSessionId === session.id ? 'auto' : 'none',
                    transition: 'opacity 0.15s ease',
                    padding: 0,
                  }}
                  title="Delete thread"
                >
                  ✕
                </button>
              </div>
            ))
          )}
        </div>
      </div>
      <SidebarUserCard user={currentUser} onLogout={onLogout} />
    </div>
  )
}
