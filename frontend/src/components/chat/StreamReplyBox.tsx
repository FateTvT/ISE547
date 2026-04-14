import type { ChatMessage } from '../../hooks/useAiChat';

type StreamReplyBoxProps = {
  messages: ChatMessage[];
  loading: boolean;
};

export function StreamReplyBox({ messages, loading }: StreamReplyBoxProps) {
  const userMessages = messages.filter((message) => message.role === 'user');
  const assistantMessages = messages.filter(
    (message) => message.role === 'assistant',
  );
  const mergedAssistantReply = assistantMessages
    .map((message) => message.content)
    .join('');

  if (messages.length === 0) {
    return (
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
    );
  }

  return (
    <>
      {userMessages.map((message) => (
        <div
          key={message.id}
          style={{
            alignSelf: 'flex-end',
            maxWidth: '80%',
            padding: '12px 16px',
            borderRadius: '12px',
            background: '#3182ce',
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
            你
          </div>
          <div>{message.content}</div>
        </div>
      ))}

      <div
        style={{
          alignSelf: 'flex-start',
          maxWidth: '80%',
          padding: '12px 16px',
          borderRadius: '12px',
          background: 'rgba(255, 255, 255, 0.08)',
          color: '#fff',
          minHeight: '48px',
          whiteSpace: 'pre-wrap',
        }}
      >
        <div
          style={{
            fontSize: '12px',
            opacity: 0.75,
            marginBottom: '4px',
          }}
        >
          AI
        </div>
        <div>{mergedAssistantReply || (loading ? '思考中...' : '')}</div>
      </div>
    </>
  );
}
