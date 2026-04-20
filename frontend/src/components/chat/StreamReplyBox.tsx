import type { ChatMessage } from '../../hooks/useAiChat';
import { ChatBubble } from './ChatBubble';
import { QuestionCard } from './QuestionCard';

type StreamReplyBoxProps = {
  messages: ChatMessage[];
  loading: boolean;
  onSelectQuestionChoice: (messageId: string, choiceId: string) => void;
  onSubmitQuestionChoice: (messageId: string) => Promise<void>;
};

export function StreamReplyBox({
  messages,
  loading,
  onSelectQuestionChoice,
  onSubmitQuestionChoice,
}: StreamReplyBoxProps) {
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
        message.role === 'interrupt' && message.questionCard ? (
          <QuestionCard
            key={message.id}
            card={message.questionCard}
            loading={loading}
            onSelect={(choiceId) => onSelectQuestionChoice(message.id, choiceId)}
            onSubmit={() => void onSubmitQuestionChoice(message.id)}
            showSubmitButton={!message.questionSubmitted}
            readOnly={Boolean(message.questionReadOnly)}
          />
        ) : (
          <ChatBubble key={message.id} role={message.role} content={message.content} />
        )
      ))}

      {loading && (
        <ChatBubble role="assistant" content="Thinking..." />
      )}
    </>
  );
}
