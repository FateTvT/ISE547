import { Button, Text } from '@chakra-ui/react'
import type { CurrentUser } from '../../service/auth.api'

type SidebarUserCardProps = {
  user: CurrentUser | null
  onLogout: () => void
}

export function SidebarUserCard({ user, onLogout }: SidebarUserCardProps) {
  return (
    <div
      style={{
        border: '1px solid rgba(255, 255, 255, 0.14)',
        borderRadius: '12px',
        padding: '12px',
        background: 'rgba(255, 255, 255, 0.03)',
      }}
    >
      <Text color="gray.300" fontSize="xs">
        Current User
      </Text>
      <Text color="white" fontWeight="bold" mt={1}>
        {user?.username ?? 'Unknown user'}
      </Text>
      <Text color="gray.400" fontSize="xs" mt={1}>
        {user?.email ?? '-'}
      </Text>
      <Button
        mt={3}
        size="sm"
        width="100%"
        onClick={onLogout}
        bg="rgba(255, 255, 255, 0.10)"
        color="white"
        border="1px solid rgba(255, 255, 255, 0.25)"
        _hover={{ bg: 'rgba(255, 255, 255, 0.16)' }}
      >
        Logout
      </Button>
    </div>
  )
}
