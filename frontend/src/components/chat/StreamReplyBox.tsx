import type { ChatMessage } from '../../hooks/useAiChat';
import { ChatBubble } from './ChatBubble';

type StreamReplyBoxProps = {
  messages: ChatMessage[];
  loading: boolean;
};

export function StreamReplyBox({ messages, loading }: StreamReplyBoxProps) {
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
        No messages yet. Send one to start.
      </div>
    );
  }

  return (
    <>
      {messages.map((message) => (
        <ChatBubble key={message.id} role={message.role} content={message.content} />
      ))}

      {loading && (
        <ChatBubble role="assistant" content="Thinking..." />
      )}
    </>
  );
}
