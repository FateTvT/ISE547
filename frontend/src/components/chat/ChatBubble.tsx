import ReactMarkdown from 'react-markdown'
import type { ChatMessage } from '../../hooks/useAiChat'

type ChatBubbleProps = {
  role: ChatMessage['role']
  content: string
}

export function ChatBubble({ role, content }: ChatBubbleProps) {
  const isUser = role === 'user'
  const isInterrupt = role === 'interrupt'
  const bubbleBackground = isUser
    ? '#3182ce'
    : isInterrupt
      ? 'rgba(214, 158, 46, 0.18)'
      : 'rgba(255, 255, 255, 0.08)'
  const title = isUser ? 'You' : isInterrupt ? 'Interrupt' : 'AI'

  return (
    <div
      style={{
        width: '100%',
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
      }}
    >
      <div
        style={{
          maxWidth: '80%',
          minWidth: '88px',
          padding: '12px 16px',
          borderRadius: '12px',
          background: bubbleBackground,
          color: '#fff',
          border: isInterrupt ? '1px solid rgba(214, 158, 46, 0.55)' : 'none',
          minHeight: '48px',
          wordBreak: 'break-word',
          overflowWrap: 'anywhere',
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
          {title}
        </div>
        {role === 'assistant' ? (
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
              ul: ({ children }) => (
                <ul style={{ margin: '4px 0', paddingLeft: '18px' }}>{children}</ul>
              ),
              ol: ({ children }) => (
                <ol style={{ margin: '4px 0', paddingLeft: '18px' }}>{children}</ol>
              ),
              li: ({ children }) => (
                <li style={{ margin: '2px 0', lineHeight: 1.4 }}>{children}</li>
              ),
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
            {content}
          </ReactMarkdown>
        ) : (
          <div>{content}</div>
        )}
      </div>
    </div>
  )
}
