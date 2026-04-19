import type { AiChatQuestionCard } from '../../schema/ai_chat_stream.schema'

type QuestionCardProps = {
  card: AiChatQuestionCard
  loading: boolean
  onSelect: (choiceId: string) => void
  onSubmit: () => void
}

export function QuestionCard({ card, loading, onSelect, onSubmit }: QuestionCardProps) {
  const selectedChoice = card.question_choices.find((choice) => choice.selected)

  return (
    <div
      style={{
        width: '100%',
        display: 'flex',
        justifyContent: 'flex-start',
      }}
    >
      <div
        style={{
          maxWidth: '80%',
          minWidth: '220px',
          padding: '12px 16px',
          borderRadius: '12px',
          background: 'rgba(214, 158, 46, 0.18)',
          border: '1px solid rgba(214, 158, 46, 0.55)',
          color: '#fff',
        }}
      >
        <div style={{ fontSize: '12px', opacity: 0.75, marginBottom: '6px' }}>Question</div>
        <div style={{ fontWeight: 600, marginBottom: '10px' }}>{card.question}</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {card.question_choices.map((choice) => (
            <button
              key={choice.choice_id}
              type="button"
              onClick={() => onSelect(choice.choice_id)}
              disabled={loading}
              style={{
                textAlign: 'left',
                padding: '10px 12px',
                borderRadius: '8px',
                background: choice.selected
                  ? 'rgba(49, 130, 206, 0.35)'
                  : 'rgba(255, 255, 255, 0.08)',
                border: choice.selected
                  ? '1px solid rgba(99, 179, 237, 0.9)'
                  : '1px solid rgba(255, 255, 255, 0.16)',
                color: '#fff',
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.7 : 1,
              }}
            >
              {choice.choice}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={onSubmit}
          disabled={!selectedChoice || loading}
          style={{
            marginTop: '12px',
            width: '100%',
            padding: '10px 12px',
            borderRadius: '8px',
            border: 'none',
            background: !selectedChoice || loading ? 'rgba(49, 130, 206, 0.45)' : '#3182ce',
            color: '#fff',
            cursor: !selectedChoice || loading ? 'not-allowed' : 'pointer',
            fontWeight: 600,
          }}
        >
          提交
        </button>
      </div>
    </div>
  )
}
