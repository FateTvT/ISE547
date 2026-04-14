import { useEffect, useState } from 'react';
import { Button, Input, Text } from '@chakra-ui/react';
import { useAiChat } from '../hooks/useAiChat';
import { StreamReplyBox } from '../components/chat/StreamReplyBox';
import {
  clearAccessToken,
  fetchCurrentUser,
  login,
  type CurrentUser,
} from '../service/auth.api';

export default function AIChatPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [prompt, setPrompt] = useState('');
  const { loading, err, messages, sendMessage, stopStream } = useAiChat();

  useEffect(() => {
    const loadCurrentUser = async () => {
      const user = await fetchCurrentUser();
      setCurrentUser(user);
    };
    void loadCurrentUser();
  }, []);

  const handleLogin = async () => {
    if (authLoading) {
      return;
    }
    setAuthError(null);
    setAuthLoading(true);
    try {
      await login({
        username: username.trim(),
        password,
      });
      const user = await fetchCurrentUser();
      if (!user) {
        throw new Error('Login succeeded, but failed to load current user.');
      }
      setCurrentUser(user);
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : 'Login failed');
      clearAccessToken();
      setCurrentUser(null);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    clearAccessToken();
    setCurrentUser(null);
  };

  const handleSend = async () => {
    if (!currentUser) {
      setAuthError('Please login before sending messages.');
      return;
    }
    await sendMessage(prompt);
  };

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
          {currentUser
            ? `Signed in as ${currentUser.username} (${currentUser.email})`
            : 'Not signed in. Please login to get a JWT token.'}
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
          <Button
            variant="outline"
            color="white"
            borderColor="rgba(255, 255, 255, 0.32)"
            onClick={handleLogout}
            disabled={!currentUser}
          >
            Logout
          </Button>
        </div>

        {authError && (
          <Text color="red.300" mt={3}>
            Auth error: {authError}
          </Text>
        )}

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
            disabled={loading || !currentUser}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                void handleSend();
              }
            }}
          />
          <Button
            bg="#3182ce"
            color="white"
            _hover={{ bg: '#2b6cb0' }}
            onClick={() => void handleSend()}
            loading={loading}
            disabled={!currentUser}
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
  );
}
