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
  const [username, setUsername] = useState('ISE547');
  const [password, setPassword] = useState('zkj666');
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
        throw new Error('登录成功，但获取用户信息失败。');
      }
      setCurrentUser(user);
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : '登录失败');
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
      setAuthError('请先登录后再发送消息。');
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
        <Text fontSize="3xl" fontWeight="bold">
          AI Chat
        </Text>
        <Text color="gray.300" mt={2}>
          输入一条消息，体验真实 SSE 流式回复。
        </Text>
        <Text color="gray.300" mt={2}>
          {currentUser
            ? `已登录：${currentUser.username} (${currentUser.email})`
            : '未登录，请先登录获取 JWT。'}
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
            placeholder="用户名"
            disabled={authLoading || Boolean(currentUser)}
          />
          <Input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="密码"
            disabled={authLoading || Boolean(currentUser)}
          />
          <Button
            colorScheme="teal"
            onClick={() => void handleLogin()}
            loading={authLoading}
            disabled={Boolean(currentUser)}
          >
            Login
          </Button>
          <Button variant="outline" onClick={handleLogout} disabled={!currentUser}>
            Logout
          </Button>
        </div>

        {authError && (
          <Text color="red.300" mt={3}>
            登录错误：{authError}
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
            placeholder="输入你的问题..."
            disabled={loading || !currentUser}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                void handleSend();
              }
            }}
          />
          <Button
            colorScheme="blue"
            onClick={() => void handleSend()}
            loading={loading}
            disabled={!currentUser}
          >
            发送
          </Button>
          <Button variant="outline" onClick={stopStream} disabled={!loading}>
            停止
          </Button>
        </div>

        {err && (
          <Text color="red.300" mt={4}>
            错误：{err}
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
