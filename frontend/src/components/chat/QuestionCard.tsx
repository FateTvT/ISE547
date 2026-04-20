import type { AiChatQuestionCard } from '../../schema/ai_chat_stream.schema'

type QuestionCardProps = {
  card: AiChatQuestionCard
  loading: boolean
  onSelect: (choiceId: string) => void
  onSubmit: () => void
  showSubmitButton?: boolean
  readOnly?: boolean
}

export function QuestionCard({
  card,
  loading,
  onSelect,
  onSubmit,
  showSubmitButton = true,
  readOnly = false,
}: QuestionCardProps) {
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
          background: '#EEF2FF',
          border: '1px solid #B9C7EA',
          color: '#1E2A4A',
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
              disabled={loading || readOnly}
              style={{
                textAlign: 'left',
                padding: '10px 12px',
                borderRadius: '8px',
                background: choice.selected
                  ? 'rgba(18, 46, 138, 0.16)'
                  : '#FFFFFF',
                border: choice.selected
                  ? '1px solid #122E8A'
                  : '1px solid #C9D3EA',
                color: '#1E2A4A',
                cursor: loading || readOnly ? 'not-allowed' : 'pointer',
                opacity: loading || readOnly ? 0.7 : 1,
              }}
            >
              {choice.choice}
            </button>
          ))}
        </div>
        {showSubmitButton && (
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
              background: !selectedChoice || loading ? '#A6B3DA' : '#122E8A',
              color: '#fff',
              cursor: !selectedChoice || loading ? 'not-allowed' : 'pointer',
              fontWeight: 600,
            }}
          >
            Submit
          </button>
        )}
      </div>
    </div>
  )
}
