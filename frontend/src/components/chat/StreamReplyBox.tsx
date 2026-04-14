import ReactMarkdown from 'react-markdown';
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
  const assistantReply = mergedAssistantReply || (loading ? 'Thinking...' : '');

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
            You
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
        <ReactMarkdown
          components={{
            p: ({ children }) => (
              <p style={{ margin: '0 0 6px', lineHeight: 1.4 }}>{children}</p>
            ),
            h1: ({ children }) => (
              <h1 style={{ margin: '8px 0 6px', lineHeight: 1.3 }}>{children}</h1>
            ),
            h2: ({ children }) => (
              <h2 style={{ margin: '8px 0 6px', lineHeight: 1.3 }}>{children}</h2>
            ),
            h3: ({ children }) => (
              <h3 style={{ margin: '8px 0 6px', lineHeight: 1.3 }}>{children}</h3>
            ),
            ul: ({ children }) => <ul style={{ margin: '4px 0', paddingLeft: '18px' }}>{children}</ul>,
            ol: ({ children }) => <ol style={{ margin: '4px 0', paddingLeft: '18px' }}>{children}</ol>,
            li: ({ children }) => <li style={{ margin: '2px 0', lineHeight: 1.4 }}>{children}</li>,
            blockquote: ({ children }) => (
              <blockquote
                style={{
                  margin: '6px 0',
                  paddingLeft: '10px',
                  borderLeft: '3px solid rgba(255, 255, 255, 0.3)',
                }}
              >
                {children}
              </blockquote>
            ),
            hr: () => (
              <hr
                style={{
                  border: 'none',
                  borderTop: '1px solid rgba(255, 255, 255, 0.2)',
                  margin: '8px 0',
                }}
              />
            ),
            code: ({ children }) => (
              <code style={{ fontFamily: 'ui-monospace, monospace' }}>{children}</code>
            ),
            pre: ({ children }) => (
              <pre
                style={{
                  margin: '6px 0',
                  padding: '8px',
                  borderRadius: '8px',
                  background: 'rgba(0, 0, 0, 0.2)',
                  overflowX: 'auto',
                }}
              >
                {children}
              </pre>
            ),
          }}
        >
          {assistantReply}
        </ReactMarkdown>
      </div>
    </>
  );
}
