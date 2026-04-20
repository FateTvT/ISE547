import type { AiChatQuestionCard } from '../../schema/ai_chat_stream.schema'

export type UserChoiceHistoryItem = {
  choice_id: string
  question_card?: AiChatQuestionCard
}

type UserChoiceHistoryPanelProps = {
  items: UserChoiceHistoryItem[]
}

export function UserChoiceHistoryPanel({ items }: UserChoiceHistoryPanelProps) {
  if (!items.length) {
    return null
  }

  return (
    <details
      style={{
        marginTop: '10px',
        background: '#F8FAFF',
        border: '1px solid #C9D3EA',
        borderRadius: '10px',
        padding: '10px 12px',
      }}
    >
      <summary
        style={{
          color: '#5B678A',
          fontSize: '13px',
          cursor: 'pointer',
          userSelect: 'none',
          fontWeight: 600,
        }}
      >
        View user choice history ({items.length})
      </summary>
      <div
        className="custom-scrollbar"
        style={{
          marginTop: '10px',
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
          maxHeight: '220px',
          overflowY: 'auto',
          paddingRight: '4px',
        }}
      >
        {items.map((item, index) => {
          const questionCard = item.question_card
          const selectedChoice = questionCard?.question_choices.find(
            (choice) => choice.choice_id === item.choice_id,
          )
          return (
            <div
              key={`${item.choice_id}-${index}`}
              style={{
                borderRadius: '8px',
                background: '#EEF2FF',
                padding: '10px',
              }}
            >
              <div style={{ color: '#1E2A4A', fontSize: '13px', fontWeight: 600 }}>
                Q{index + 1}: {questionCard?.question ?? 'Question unavailable'}
              </div>
              {questionCard ? (
                <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {questionCard.question_choices.map((choice) => {
                    const isSelected = choice.choice_id === item.choice_id
                    return (
                      <div
                        key={choice.choice_id}
                        style={{
                          color: isSelected ? '#122E8A' : '#5B678A',
                          fontSize: '12px',
                        }}
                      >
                        {isSelected ? '✓ ' : '• '}
                        {choice.choice}
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div style={{ marginTop: '8px', color: '#7A86A8', fontSize: '12px' }}>
                  Choice details unavailable; recorded choice_id: {item.choice_id}
                </div>
              )}
              {selectedChoice && (
                <div style={{ marginTop: '8px', color: '#122E8A', fontSize: '12px' }}>
                  Selected: {selectedChoice.choice}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </details>
  )
}
