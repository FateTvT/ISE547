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
        background: 'rgba(255, 255, 255, 0.04)',
        border: '1px solid rgba(255, 255, 255, 0.12)',
        borderRadius: '10px',
        padding: '10px 12px',
      }}
    >
      <summary
        style={{
          color: '#cbd5e1',
          fontSize: '13px',
          cursor: 'pointer',
          userSelect: 'none',
          fontWeight: 600,
        }}
      >
        查看用户选择历史（{items.length}）
      </summary>
      <div
        style={{
          marginTop: '10px',
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
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
                background: 'rgba(15, 23, 42, 0.55)',
                padding: '10px',
              }}
            >
              <div style={{ color: '#e2e8f0', fontSize: '13px', fontWeight: 600 }}>
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
                          color: isSelected ? '#90cdf4' : '#cbd5e1',
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
                <div style={{ marginTop: '8px', color: '#94a3b8', fontSize: '12px' }}>
                  选项详情缺失，已记录 choice_id: {item.choice_id}
                </div>
              )}
              {selectedChoice && (
                <div style={{ marginTop: '8px', color: '#90cdf4', fontSize: '12px' }}>
                  已选: {selectedChoice.choice}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </details>
  )
}
