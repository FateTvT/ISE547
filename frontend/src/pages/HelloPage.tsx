import { useState } from 'react';
import { Button, Input, Text } from '@chakra-ui/react';
import { useAiChat } from '../hooks/useAiChat';

export default function AIChatPage() {
  const [prompt, setPrompt] = useState('');
  const { loading, err, messages, sendMessage, stopStream } = useAiChat();

  const handleSend = async () => {
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
          输入一条消息，体验 mock SSE 流式回复。
        </Text>

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
            disabled={loading}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                void handleSend();
              }
            }}
          />
          <Button colorScheme="blue" onClick={() => void handleSend()} loading={loading}>
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
          {messages.length === 0 ? (
            <div
              style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                border: '1px dashed rgba(255, 255, 255, 0.2)',
                borderRadius: '12px',
                color: '#cbd5e1',
              }}
            >
              暂无消息，先发一条试试。
            </div>
          ) : (
            messages.map((message) => (
              <div
                key={message.id}
                style={{
                  alignSelf: message.role === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '80%',
                  padding: '12px 16px',
                  borderRadius: '12px',
                  background:
                    message.role === 'user' ? '#3182ce' : 'rgba(255, 255, 255, 0.08)',
                  color: '#fff',
                }}
              >
                <div
                  style={{
                    fontSize: '12px',
                    opacity: 0.75,
                    marginBottom: '4px',
                  }}
                >
                  {message.role === 'user' ? '你' : 'AI'}
                </div>
                <div>{message.content}</div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
