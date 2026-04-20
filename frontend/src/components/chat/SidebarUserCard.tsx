import { Button, Text } from '@chakra-ui/react'
import type { CurrentUser } from '../../service/auth.api'

type SidebarUserCardProps = {
  user: CurrentUser | null
  onLogout: () => void
}

export function SidebarUserCard({ user, onLogout }: SidebarUserCardProps) {
  const primaryColor = '#122E8A'
  const secondaryColor = '#5A6FB2'
  const textPrimary = '#1E2A4A'
  const textMuted = '#5B678A'

  return (
    <div
      style={{
        border: '1px solid #C9D3EA',
        borderRadius: '12px',
        padding: '12px',
        background: '#F8FAFF',
      }}
    >
      <Text color={textMuted} fontSize="xs">
        Current User
      </Text>
      <Text color={textPrimary} fontWeight="bold" mt={1}>
        {user?.username ?? 'Unknown user'}
      </Text>
      <Text color={textMuted} fontSize="xs" mt={1}>
        {user?.email ?? '-'}
      </Text>
      <Button
        mt={3}
        size="sm"
        width="100%"
        onClick={onLogout}
        bg={primaryColor}
        color="white"
        border={`1px solid ${primaryColor}`}
        _hover={{ bg: '#0E246D' }}
      >
        Logout
      </Button>
    </div>
  )
}
